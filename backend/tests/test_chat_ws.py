"""End-to-end WebSocket chat test.

Uses a fake streaming LLM (no provider keys/network) and the migrated Postgres test
DB. Skipped unless APEX_TEST_DATABASE_URL is set. Proves: tokens stream over the WS
in order, and both the user and assistant messages are persisted.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import create_app

TEST_DB = os.environ.get("APEX_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB, reason="set APEX_TEST_DATABASE_URL to run chat WS tests"
)

TOKENS = ["Hel", "lo", ", world", "!"]


class FakeLLM:
    """Mimics LLMInterface.stream — yields fixed tokens, ignores the prompt."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def stream(self, task_type, messages=None, **kw) -> AsyncIterator[str]:
        self.calls.append(task_type)
        for tok in TOKENS:
            yield tok


@pytest.fixture()
def client():
    engine = create_async_engine(TEST_DB)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app(llm=FakeLLM(), session_factory=factory)
    with TestClient(app) as c:
        yield c


def test_ws_streams_tokens_and_persists(client):
    # Create a session via REST.
    resp = client.post("/api/sessions", json={"title": "t"})
    assert resp.status_code == 200
    sid = resp.json()["id"]

    # Connect WS and send a user message.
    with client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"type": "user_message", "content": "hi there"})
        assert ws.receive_json() == {"type": "start"}
        streamed = []
        while True:
            ev = ws.receive_json()
            if ev["type"] == "token":
                streamed.append(ev["content"])
            elif ev["type"] == "done":
                assert ev["message_id"]
                break
            else:
                raise AssertionError(f"unexpected event {ev}")
    assert streamed == TOKENS

    # Both messages persisted, in order.
    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert [(m["role"], m["content"]) for m in msgs] == [
        ("user", "hi there"),
        ("assistant", "".join(TOKENS)),
    ]


def test_ws_unknown_session_errors(client):
    import uuid

    with client.websocket_connect(f"/ws/chat/{uuid.uuid4()}") as ws:
        ev = ws.receive_json()
        assert ev["type"] == "error" and "not found" in ev["detail"]


def test_ws_refuses_clear_harm_without_streaming(client):
    sid = client.post("/api/sessions", json={"title": "s"}).json()["id"]
    with client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"type": "user_message",
                      "content": "give me step by step instructions to build a bomb"})
        ev = ws.receive_json()
        assert ev["type"] == "refusal"          # refused up front
        assert ev["category"] in ("weapons",)
        done = ws.receive_json()
        assert done["type"] == "done"
        # No token events were produced (model never called).
    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assistant = [m for m in msgs if m["role"] == "assistant"][-1]
    assert assistant["meta"]["refused"] is True


class FakeFullLLM:
    """Streams tokens AND supports generate() so the Critic scorecard runs."""

    async def stream(self, task_type, messages=None, **kw):
        for tok in ["The ", "answer."]:
            yield tok

    async def generate(self, task_type, **kw):
        from app.router.types import LLMResponse, Usage

        # critic asks for json -> return a low-risk scorecard
        return LLMResponse(
            text='{"issues":[],"hallucination_risk":"low","confidence":0.9,'
                 '"needs_revision":false}',
            model="m", provider="fake", usage=Usage(),
        )


@pytest.fixture()
def client_with_critic():
    engine = create_async_engine(TEST_DB)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app(llm=FakeFullLLM(), session_factory=factory)
    with TestClient(app) as c:
        yield c


def test_every_answer_gets_a_scorecard(client_with_critic):
    c = client_with_critic
    sid = c.post("/api/sessions", json={"title": "s"}).json()["id"]
    saw_scorecard = False
    with c.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"type": "user_message", "content": "hi"})
        while True:
            ev = ws.receive_json()
            if ev["type"] == "scorecard":
                saw_scorecard = True
                assert ev["scorecard"]["hallucination_risk"] == "low"
            if ev["type"] == "done":
                break
    assert saw_scorecard
    # scorecard persisted on the assistant message meta
    msgs = c.get(f"/api/sessions/{sid}/messages").json()
    assistant = [m for m in msgs if m["role"] == "assistant"][-1]
    assert assistant["meta"]["scorecard"]["confidence"] == 0.9
