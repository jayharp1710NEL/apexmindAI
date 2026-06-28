"""Worker job handling: a queued job runs in the sandbox and returns a result."""

from __future__ import annotations

import json

from worker import handle_job


def test_handle_job_runs_code_and_returns_result():
    raw = json.dumps({
        "id": "job-123",
        "code": "print(2 + 3)",
        "timeout_seconds": 5,
        "mem_mb": 128,
        "max_output_bytes": 1000,
    }).encode()
    job_id, payload = handle_job(raw)
    assert job_id == "job-123"
    assert payload["status"] == "ok"
    assert "5" in payload["stdout"]


def test_handle_job_reports_sandbox_error():
    raw = json.dumps({"id": "j2", "code": "raise ValueError('x')"}).encode()
    job_id, payload = handle_job(raw)
    assert job_id == "j2"
    assert payload["status"] == "error"
    assert "ValueError" in payload["stderr"]
