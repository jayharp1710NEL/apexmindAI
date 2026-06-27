"""Postgres-backed audit tests.

Skipped automatically unless a reachable database is configured via the
APEX_TEST_DATABASE_URL env var (the schema must already be migrated). These prove:
  - a model call through BaseAdapter writes request + response audit rows;
  - the persisted chain verifies;
  - the DB rejects UPDATE/DELETE on audit_log (append-only).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.logger import AuditLogger
from app.router.adapters.base import BaseAdapter
from app.router.types import EmbedRequest, EmbedResponse, LLMRequest, LLMResponse, Usage

TEST_DB = os.environ.get("APEX_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB, reason="set APEX_TEST_DATABASE_URL to run audit integration tests"
)


@pytest.fixture()
async def session_factory():
    engine = create_async_engine(TEST_DB, poolclass=None)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    # clean slate (DELETE is blocked by the trigger, so TRUNCATE which the trigger
    # does not cover for a fresh test schema; if it's blocked, the tests still work
    # additively).
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_append_only"))
            await conn.execute(text("DELETE FROM audit_log"))
            await conn.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_append_only"))
        except Exception:
            pass
    yield factory
    await engine.dispose()


class FakeAdapter(BaseAdapter):
    provider = "anthropic"

    async def _generate(self, req: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text="hello", model=req.model or "m", provider=self.provider,
            usage=Usage(input_tokens=3, output_tokens=4), finish_reason="stop",
        )

    async def _embed(self, req: EmbedRequest) -> EmbedResponse:  # pragma: no cover
        raise NotImplementedError


async def test_model_call_writes_audited_chain(session_factory):
    logger = AuditLogger(session_factory)
    adapter = FakeAdapter(api_key="k", audit_hook=logger.model_audit_hook())

    await adapter.generate(LLMRequest(messages=[], model="claude-x"))

    async with session_factory() as s:
        count = await s.scalar(text("SELECT count(*) FROM audit_log"))
        phases = (
            await s.execute(
                text("SELECT payload->>'phase' FROM audit_log ORDER BY id")
            )
        ).scalars().all()
    assert count == 2  # request + response
    assert phases == ["request", "response"]

    check = await logger.verify()
    assert check.ok and check.count == 2


async def test_audit_log_is_append_only(session_factory):
    logger = AuditLogger(session_factory)
    await logger.append(actor="system", event_type="test", payload={"x": 1})

    async with session_factory() as s:
        with pytest.raises(Exception):
            await s.execute(text("UPDATE audit_log SET actor='hacker'"))
            await s.commit()
    async with session_factory() as s:
        with pytest.raises(Exception):
            await s.execute(text("DELETE FROM audit_log"))
            await s.commit()
