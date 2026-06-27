"""initial schema: 18 core tables + pgvector

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-27
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBED_DIM = 1536

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("name", sa.String(200)),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )

    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "user_id", UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )

    # --- sessions ---
    op.create_table(
        "sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "project_id", UUID,
            sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "user_id", UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("title", sa.String(300)),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "session_id", UUID,
            sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer),
        sa.Column("meta", JSONB),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "role in ('user','assistant','system','tool')", name="ck_message_role"
        ),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])

    # --- runs ---
    op.create_table(
        "runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "session_id", UUID,
            sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("goal", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("plan", JSONB),
        sa.Column("max_steps", sa.Integer),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", TS),
    )
    op.create_index("ix_runs_session_id", "runs", ["session_id"])

    # --- steps ---
    op.create_table(
        "steps",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "run_id", UUID,
            sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("idx", sa.Integer, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("agent", sa.String(40)),
        sa.Column("tool", sa.String(60)),
        sa.Column("tool_level", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input", JSONB),
        sa.Column("output", JSONB),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("tool_level between 0 and 5", name="ck_step_tool_level"),
        sa.UniqueConstraint("run_id", "idx", name="uq_step_run_idx"),
    )
    op.create_index("ix_steps_run_id", "steps", ["run_id"])

    # --- audit_log (append-only, hash-chained) ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ts", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("session_id", UUID),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("prev_hash", sa.String(64)),
        sa.Column("entry_hash", sa.String(64), nullable=False, unique=True),
    )
    op.create_index("ix_audit_event_type", "audit_log", ["event_type"])
    op.create_index("ix_audit_session_id", "audit_log", ["session_id"])

    # --- project_facts ---
    op.create_table(
        "project_facts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "project_id", UUID,
            sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("scope", sa.String(20), nullable=False, server_default="project"),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "key", name="uq_fact_project_key"),
    )
    op.create_index("ix_facts_project_id", "project_facts", ["project_id"])

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "project_id", UUID,
            sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(120)),
        sa.Column("size_bytes", sa.Integer),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])

    # --- doc_chunks ---
    op.create_table(
        "doc_chunks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "document_id", UUID,
            sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("idx", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer),
        sa.Column("embedding", Vector(EMBED_DIM)),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("document_id", "idx", name="uq_docchunk_doc_idx"),
    )
    op.create_index("ix_docchunks_document_id", "doc_chunks", ["document_id"])

    # --- semantic_chunks ---
    op.create_table(
        "semantic_chunks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "document_id", UUID,
            sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("idx", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("token_count", sa.Integer),
        sa.Column("embedding", Vector(EMBED_DIM)),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("document_id", "idx", name="uq_semchunk_doc_idx"),
    )
    op.create_index("ix_semchunks_document_id", "semantic_chunks", ["document_id"])

    # --- tool_results ---
    op.create_table(
        "tool_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "step_id", UUID,
            sa.ForeignKey("steps.id", ondelete="SET NULL"),
        ),
        sa.Column("tool_name", sa.String(60), nullable=False),
        sa.Column("level", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stdout", sa.Text),
        sa.Column("stderr", sa.Text),
        sa.Column("return_code", sa.Integer),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("result", JSONB),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_toolresults_step_id", "tool_results", ["step_id"])

    # --- tool_registry ---
    op.create_table(
        "tool_registry",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(60), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("input_schema", JSONB),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("level between 0 and 5", name="ck_tool_level"),
    )

    # --- benchmark_runs ---
    op.create_table(
        "benchmark_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("suite_name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("summary", JSONB),
        sa.Column("started_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", TS),
    )

    # --- benchmark_results ---
    op.create_table(
        "benchmark_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "benchmark_run_id", UUID,
            sa.ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("test_id", sa.String(120), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("score", sa.Float),
        sa.Column("detail", JSONB),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_benchresults_run_id", "benchmark_results", ["benchmark_run_id"]
    )

    # --- safety_incidents ---
    op.create_table(
        "safety_incidents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("ts", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("decision", sa.String(20)),
        sa.Column("session_id", UUID),
        sa.Column("detail", JSONB),
    )
    op.create_index("ix_incidents_session_id", "safety_incidents", ["session_id"])

    # --- prompt_versions ---
    op.create_table(
        "prompt_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )

    # Append-only guard: block UPDATE/DELETE on audit_log at the DB level.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION apex_block_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only; % is not permitted', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_append_only
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION apex_block_audit_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_append_only ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS apex_block_audit_mutation()")
    for table in [
        "prompt_versions",
        "safety_incidents",
        "benchmark_results",
        "benchmark_runs",
        "tool_registry",
        "tool_results",
        "semantic_chunks",
        "doc_chunks",
        "documents",
        "project_facts",
        "audit_log",
        "steps",
        "runs",
        "messages",
        "sessions",
        "projects",
        "users",
    ]:
        op.drop_table(table)
