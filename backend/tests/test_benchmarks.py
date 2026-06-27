"""Benchmark runner tests.

Without a DB, the runner still produces >=10 deterministic pass/fail results (the
acceptance bar). With a DB, the 3 DB-backed checks also run and pass.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.benchmarks.runner import run_suite

TEST_DB = os.environ.get("APEX_TEST_DATABASE_URL")


async def test_suite_runs_without_db_meets_min_10():
    out = await run_suite(session_factory=None, llm=None)
    summary = out["summary"]
    # >=10 objective pass/fail results required by the acceptance criteria.
    assert summary["scored"] >= 10
    # All deterministic, no-DB checks should pass.
    assert summary["failed"] == 0, [r for r in out["results"] if r["passed"] is False]
    cats = {r["category"] for r in out["results"]}
    assert {"coding", "math", "sandbox", "safety", "injection", "permission"} <= cats


@pytest.mark.skipif(not TEST_DB, reason="set APEX_TEST_DATABASE_URL")
async def test_suite_with_db_runs_all_and_passes():
    engine = create_async_engine(TEST_DB)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        out = await run_suite(session_factory=factory, llm=None)
        summary = out["summary"]
        assert summary["skipped"] == 0       # DB checks ran too
        assert summary["scored"] >= 14
        assert summary["failed"] == 0, [r for r in out["results"] if r["passed"] is False]
        assert out["run_id"] is not None     # persisted
    finally:
        await engine.dispose()
