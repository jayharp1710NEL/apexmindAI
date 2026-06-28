"""API-side code_exec Redis transport (worker mode) with a fake async Redis.

Proves make_redis_code_exec enqueues a job and maps the worker's result back into a
ToolResult — without needing a live Redis or worker.
"""

from __future__ import annotations

import json

from app.tools.impl.code_exec import make_redis_code_exec


class FakeAsyncRedis:
    def __init__(self, result_payload: dict | None):
        self.result = result_payload
        self.pushed: list[tuple[str, str]] = []

    async def rpush(self, key, value):
        self.pushed.append((key, value))

    async def blpop(self, key, timeout=0):
        if self.result is None:
            return None
        return (key, json.dumps(self.result))


async def test_redis_transport_returns_worker_result():
    payload = {"status": "ok", "stdout": "hi\n", "stderr": "", "return_code": 0,
               "duration_ms": 3, "timed_out": False}
    redis = FakeAsyncRedis(payload)
    impl = make_redis_code_exec(redis)
    res = await impl({"code": "print('hi')"})
    assert res.status == "ok"
    assert res.stdout == "hi\n"
    assert res.level == 2
    # the job was actually enqueued
    assert redis.pushed and "tooljobs" in redis.pushed[0][0]
    enqueued = json.loads(redis.pushed[0][1])
    assert enqueued["code"] == "print('hi')"


async def test_redis_transport_times_out_when_no_result():
    impl = make_redis_code_exec(FakeAsyncRedis(None), overall_timeout=1)
    res = await impl({"code": "print('x')"})
    assert res.status == "timeout"
    assert "did not return" in (res.error or "")
