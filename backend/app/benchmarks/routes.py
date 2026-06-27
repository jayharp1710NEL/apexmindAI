"""Benchmark API: run the suite, list past runs, fetch a run's results."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.benchmarks.runner import run_suite

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


@router.post("/run")
async def run(request: Request) -> dict:
    return await run_suite(
        session_factory=request.app.state.session_factory,
        llm=request.app.state.llm,
    )


@router.get("")
async def list_runs(request: Request) -> list[dict]:
    from app.db.models import BenchmarkRun

    factory = request.app.state.session_factory
    async with factory() as s:
        rows = (
            await s.scalars(
                select(BenchmarkRun).order_by(BenchmarkRun.started_at.desc()).limit(50)
            )
        ).all()
    return [
        {"id": str(r.id), "suite_name": r.suite_name, "status": r.status,
         "summary": r.summary,
         "started_at": r.started_at.isoformat() if r.started_at else None}
        for r in rows
    ]


@router.get("/{run_id}")
async def get_run(run_id: uuid.UUID, request: Request) -> dict:
    from app.db.models import BenchmarkResult, BenchmarkRun

    factory = request.app.state.session_factory
    async with factory() as s:
        run = await s.get(BenchmarkRun, run_id)
        if run is None:
            raise HTTPException(404, "run not found")
        results = (
            await s.scalars(
                select(BenchmarkResult).where(
                    BenchmarkResult.benchmark_run_id == run_id
                )
            )
        ).all()
    return {
        "id": str(run.id), "suite_name": run.suite_name, "status": run.status,
        "summary": run.summary,
        "results": [
            {"test_id": r.test_id, "category": r.category, "passed": r.passed,
             "detail": r.detail}
            for r in results
        ],
    }
