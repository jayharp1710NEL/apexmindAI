"""Benchmark runner: execute a suite, persist results, return a summary."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.benchmarks.checks import REGISTRY, CheckContext

SUITE_DIR = Path(__file__).resolve().parent / "suites"


def load_suite(name: str = "mvp_suite") -> dict:
    with open(SUITE_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)


async def run_suite(
    *, session_factory=None, llm=None, suite_name: str = "mvp_suite"
) -> dict:
    suite = load_suite(suite_name)
    ctx = CheckContext(session_factory=session_factory, llm=llm)

    # Persist a benchmark_runs row up front (if a DB is available).
    run_id = None
    if session_factory is not None:
        from app.db.models import BenchmarkRun

        async with session_factory() as s, s.begin():
            run = BenchmarkRun(suite_name=suite_name, status="running")
            s.add(run)
            await s.flush()
            run_id = run.id

    results: list[dict] = []
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "failed": 0,
                                                                  "skipped": 0})
    for test in suite["tests"]:
        tid, category = test["id"], test["category"]
        entry = REGISTRY.get(tid)
        if entry is None:
            results.append({"test_id": tid, "category": category, "passed": False,
                            "detail": {"error": "unknown checker"}})
            by_category[category]["failed"] += 1
            continue
        fn, requires_db = entry
        if requires_db and session_factory is None:
            results.append({"test_id": tid, "category": category, "passed": None,
                            "detail": {"skipped": "requires db"}})
            by_category[category]["skipped"] += 1
            continue
        started = time.monotonic()
        try:
            passed, detail = await fn(ctx)
        except Exception as exc:
            passed, detail = False, {"error": f"{type(exc).__name__}: {exc}"}
        detail = {**detail, "ms": int((time.monotonic() - started) * 1000)}
        results.append({"test_id": tid, "category": category, "passed": passed,
                        "detail": detail})
        by_category[category]["passed" if passed else "failed"] += 1

    scored = [r for r in results if r["passed"] is not None]
    passed_n = sum(1 for r in scored if r["passed"])
    summary = {
        "suite": suite_name,
        "total": len(results),
        "scored": len(scored),
        "passed": passed_n,
        "failed": len(scored) - passed_n,
        "skipped": len(results) - len(scored),
        "by_category": dict(by_category),
    }

    if session_factory is not None and run_id is not None:
        from app.db.models import BenchmarkResult, BenchmarkRun

        async with session_factory() as s, s.begin():
            for r in results:
                if r["passed"] is None:
                    continue
                s.add(BenchmarkResult(
                    benchmark_run_id=run_id, test_id=r["test_id"],
                    category=r["category"], passed=bool(r["passed"]),
                    score=1.0 if r["passed"] else 0.0, detail=r["detail"],
                ))
            run = await s.get(BenchmarkRun, run_id)
            if run:
                run.status = "completed"
                run.summary = summary
                run.finished_at = datetime.now(timezone.utc)

    return {"run_id": str(run_id) if run_id else None, "summary": summary,
            "results": results}
