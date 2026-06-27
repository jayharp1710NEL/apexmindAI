"""ORM models for ApexMind.

Eighteen tables backing the command center. Notable design points:

- `audit_log` is append-only with a hash chain (`prev_hash` -> `entry_hash`) so
  tampering is detectable. The application never updates or deletes rows here.
- Vector columns (`doc_chunks.embedding`, `semantic_chunks.embedding`) use pgvector.
  `EMBED_DIM` is fixed at DDL time; changing embedding models with a different
  dimension requires a migration.
- Timestamps are timezone-aware and server-defaulted.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# Embedding dimension (OpenAI text-embedding-3-small / Google text-embedding-004).
# Fixed at DDL time; a different-dimension model needs a migration.
EMBED_DIM = 1536


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --------------------------------------------------------------------------- #
# Identity & workspace
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = _created_at()

    projects: Mapped[list[Project]] = relationship(back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()

    user: Mapped[User] = relationship(back_populates="projects")
    sessions: Mapped[list[Session]] = relationship(back_populates="project")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = _created_at()

    project: Mapped[Project] = relationship(back_populates="sessions")
    messages: Mapped[list[Message]] = relationship(back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user|assistant|system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict | None] = mapped_column(JSONB)  # scorecard, citations, etc.
    created_at: Mapped[datetime] = _created_at()

    session: Mapped[Session] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint(
            "role in ('user','assistant','system','tool')", name="ck_message_role"
        ),
    )


# --------------------------------------------------------------------------- #
# Orchestration: runs & steps
# --------------------------------------------------------------------------- #
class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending|running|paused|completed|failed|stopped
    plan: Mapped[dict | None] = mapped_column(JSONB)
    max_steps: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list[Step]] = relationship(back_populates="run")


class Step(Base):
    __tablename__ = "steps"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    agent: Mapped[str | None] = mapped_column(String(40))
    tool: Mapped[str | None] = mapped_column(String(60))
    tool_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending|awaiting_approval|running|done|skipped|failed
    input: Mapped[dict | None] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()

    run: Mapped[Run] = relationship(back_populates="steps")

    __table_args__ = (
        CheckConstraint("tool_level between 0 and 5", name="ck_step_tool_level"),
        UniqueConstraint("run_id", "idx", name="uq_step_run_idx"),
    )


# --------------------------------------------------------------------------- #
# Audit log (append-only, hash-chained)
# --------------------------------------------------------------------------- #
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = _created_at()
    actor: Mapped[str] = mapped_column(String(80), nullable=False)  # system|user|agent name
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # e.g. model_call, tool_call, approval, estop, safety_decision
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


# --------------------------------------------------------------------------- #
# Memory
# --------------------------------------------------------------------------- #
class ProjectFact(Base):
    __tablename__ = "project_facts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    scope: Mapped[str] = mapped_column(String(20), default="project", nullable=False)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_fact_project_key"),
    )


# --------------------------------------------------------------------------- #
# RAG: documents & chunks
# --------------------------------------------------------------------------- #
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created_at()

    chunks: Mapped[list[DocChunk]] = relationship(back_populates="document")
    semantic_chunks: Mapped[list[SemanticChunk]] = relationship(
        back_populates="document"
    )


class DocChunk(Base):
    __tablename__ = "doc_chunks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    created_at: Mapped[datetime] = _created_at()

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "idx", name="uq_docchunk_doc_idx"),
    )


class SemanticChunk(Base):
    """Semantic (meaning-based) chunking variant, kept alongside fixed-size chunks."""

    __tablename__ = "semantic_chunks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    created_at: Mapped[datetime] = _created_at()

    document: Mapped[Document] = relationship(back_populates="semantic_chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "idx", name="uq_semchunk_doc_idx"),
    )


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
class ToolResult(Base):
    __tablename__ = "tool_results"

    id: Mapped[uuid.UUID] = _uuid_pk()
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("steps.id", ondelete="SET NULL"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(60), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # ok|error|denied|timeout
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    return_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()


class ToolRegistry(Base):
    __tablename__ = "tool_registry"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # required permission level
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    input_schema: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        CheckConstraint("level between 0 and 5", name="ck_tool_level"),
    )


# --------------------------------------------------------------------------- #
# Benchmarks
# --------------------------------------------------------------------------- #
class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    suite_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    summary: Mapped[dict | None] = mapped_column(JSONB)  # pass/fail counts, etc.
    started_at: Mapped[datetime] = _created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    results: Mapped[list[BenchmarkResult]] = relationship(back_populates="run")


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    id: Mapped[uuid.UUID] = _uuid_pk()
    benchmark_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_id: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()

    run: Mapped[BenchmarkRun] = relationship(back_populates="results")


# --------------------------------------------------------------------------- #
# Safety & prompts
# --------------------------------------------------------------------------- #
class SafetyIncident(Base):
    __tablename__ = "safety_incidents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    ts: Mapped[datetime] = _created_at()
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    # e.g. refusal, injection_detected, level5_blocked, estop
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    decision: Mapped[str | None] = mapped_column(String(20))  # allow|refuse|escalate
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    detail: Mapped[dict | None] = mapped_column(JSONB)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(80), nullable=False)  # orchestrator|critic|...
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )
