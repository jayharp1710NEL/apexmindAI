"""Tool worker: pull code-exec jobs from Redis, run them in the sandbox, return
results. Runs as a separate, network-restricted, resource-limited container.

Job (pushed by the API onto JOB_QUEUE) is JSON:
    {"id": str, "code": str, "timeout_seconds": int, "mem_mb": int,
     "max_output_bytes": int}
Result is pushed onto RESULT_PREFIX + id as JSON (ExecResult).
"""

from __future__ import annotations

import json
import os
import time

from executor import run_code

JOB_QUEUE = os.environ.get("TOOL_JOB_QUEUE", "apex:tooljobs")
RESULT_PREFIX = os.environ.get("TOOL_RESULT_PREFIX", "apex:toolresult:")
RESULT_TTL_SECONDS = int(os.environ.get("TOOL_RESULT_TTL", "120"))


def _connect():
    import redis

    return redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))


def handle_job(raw: bytes) -> tuple[str, dict]:
    job = json.loads(raw)
    result = run_code(
        job["code"],
        timeout_seconds=int(job.get("timeout_seconds", 10)),
        mem_mb=int(job.get("mem_mb", 256)),
        max_output_bytes=int(job.get("max_output_bytes", 65536)),
    )
    return job["id"], result.to_dict()


def main() -> None:  # pragma: no cover - integration loop
    client = _connect()
    print(f"[tool-worker] waiting for jobs on {JOB_QUEUE}", flush=True)
    while True:
        item = client.blpop(JOB_QUEUE, timeout=5)
        if item is None:
            continue
        _, raw = item
        try:
            job_id, payload = handle_job(raw)
        except Exception as exc:
            print(f"[tool-worker] bad job: {exc!r}", flush=True)
            continue
        key = RESULT_PREFIX + job_id
        client.rpush(key, json.dumps(payload))
        client.expire(key, RESULT_TTL_SECONDS)
        print(f"[tool-worker] completed job {job_id} at {time.time()}", flush=True)


if __name__ == "__main__":
    main()
