"""Memory-lite tests: conservative extraction, upsert, list/delete, formatting."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.chat import repository as repo
from app.memory import facts as facts_repo
from app.memory.facts import format_facts_for_prompt
from app.memory.memory_step import extract_and_store_facts
from app.router.types import LLMResponse, Usage

TEST_DB = os.environ.get("APEX_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DB, reason="set APEX_TEST_DATABASE_URL to run memory tests"
)


class FakeMemLLM:
    def __init__(self, payload: str):
        self.payload = payload

    async def generate(self, task_type, **kw):
        return LLMResponse(text=self.payload, model="m", provider="fake", usage=Usage())


@pytest.fixture()
async def factory():
    engine = create_async_engine(TEST_DB)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM project_facts"))
    yield f
    await engine.dispose()


async def _project(factory):
    _, pid = await repo.get_or_create_default_context(factory)
    return pid


async def test_memory_step_stores_high_confidence_only(factory):
    pid = await _project(factory)
    payload = (
        '{"facts":['
        '{"key":"preferred_language","value":"Python","confidence":0.95,"scope":"project"},'
        '{"key":"random_guess","value":"maybe","confidence":0.2,"scope":"project"}'
        ']}'
    )
    stored = await extract_and_store_facts(
        llm=FakeMemLLM(payload), session_factory=factory, project_id=pid,
        conversation="user: I prefer Python for this project",
    )
    assert len(stored) == 1  # the 0.2-confidence fact was dropped
    assert stored[0]["key"] == "preferred_language"

    async with factory() as s:
        rows = await facts_repo.list_facts(s, pid)
    assert len(rows) == 1 and rows[0].value == "Python"


async def test_upsert_overwrites_same_key(factory):
    pid = await _project(factory)
    async with factory() as s, s.begin():
        await facts_repo.upsert_fact(s, project_id=pid, key="k", value="v1", confidence=0.9)
    async with factory() as s, s.begin():
        await facts_repo.upsert_fact(s, project_id=pid, key="k", value="v2", confidence=0.9)
    async with factory() as s:
        rows = await facts_repo.list_facts(s, pid)
    assert len(rows) == 1 and rows[0].value == "v2"


async def test_list_and_delete(factory):
    pid = await _project(factory)
    async with factory() as s, s.begin():
        f = await facts_repo.upsert_fact(s, project_id=pid, key="k", value="v", confidence=1.0)
        fact_id = f.id
    async with factory() as s, s.begin():
        ok = await facts_repo.delete_fact(s, fact_id)
    assert ok is True
    async with factory() as s:
        rows = await facts_repo.list_facts(s, pid)
    assert rows == []


def test_format_facts_empty_is_blank():
    assert format_facts_for_prompt([]) == ""
