"""code_exec (Level 2) — run untrusted Python in the sandboxed tool-worker.

Two transports, same ToolResult shape:

  * `make_redis_code_exec` — production: push a job to Redis, await the worker's
    result. The API process never executes untrusted code itself.
  * `make_local_code_exec` — dev/tests: run the sandbox executor in-process (still a
    network-less, resource-limited subprocess) without needing a separate worker.

Both return an async impl `(args) -> ToolResult` suitable for ToolManager, where
`args = {"code": "<python source>"}`.
"""

from __future__ import annotations

import json
import uuid

from app.config import settings
from app.tools.schema import ToolResult


def _result_from_exec(payload: dict) -> ToolResult:
    return ToolResult(
        tool_name="code_exec",
        level=2,
        status=payload.get("status", "error"),
        stdout=payload.get("stdout"),
        stderr=payload.get("stderr"),
        return_code=payload.get("return_code"),
        duration_ms=payload.get("duration_ms"),
        result={"timed_out": payload.get("timed_out", False)},
    )


def make_local_code_exec():
    async def _impl(args: dict) -> ToolResult:
        from app.tools.sandbox import run_code

        code = args.get("code", "")
        res = run_code(
            code,
            timeout_seconds=settings.sandbox_timeout_seconds,
            mem_mb=settings.sandbox_mem_mb,
            max_output_bytes=settings.sandbox_max_output_bytes,
        )
        return _result_from_exec(res.to_dict())

    return _impl


def make_redis_code_exec(redis_client, *, overall_timeout: float | None = None):
    job_queue = "apex:tooljobs"
    result_prefix = "apex:toolresult:"
    wait = overall_timeout or (settings.sandbox_timeout_seconds + 10)

    async def _impl(args: dict) -> ToolResult:
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "code": args.get("code", ""),
            "timeout_seconds": settings.sandbox_timeout_seconds,
            "mem_mb": settings.sandbox_mem_mb,
            "max_output_bytes": settings.sandbox_max_output_bytes,
        }
        await redis_client.rpush(job_queue, json.dumps(job))
        item = await redis_client.blpop(result_prefix + job_id, timeout=int(wait))
        if item is None:
            return ToolResult(
                tool_name="code_exec", level=2, status="timeout",
                error="tool-worker did not return a result in time",
            )
        _, raw = item
        return _result_from_exec(json.loads(raw))

    return _impl
