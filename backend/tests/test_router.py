"""Router unit tests — fully offline (no vendor SDK, no network).

Fake adapters subclass BaseAdapter, so the audited template path in base.py is
exercised too: these tests also prove the audit hook fires on every model call.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.router.adapters.base import BaseAdapter
from app.router.router import (
    AllCandidatesFailed,
    NoAvailableProvider,
    Router,
)
from app.router.types import (
    EmbedRequest,
    EmbedResponse,
    LLMRequest,
    LLMResponse,
    Message,
    Usage,
)

ROUTING = {
    "default_provider": "anthropic",
    "task_types": {
        "reasoning": [
            {"provider": "anthropic", "model": "claude-x"},
            {"provider": "openai", "model": "gpt-x"},
            {"provider": "google", "model": "gemini-x"},
        ],
        "embeddings": [
            {"provider": "openai", "model": "embed-x"},
        ],
    },
}


class FakeAdapter(BaseAdapter):
    def __init__(self, provider: str, *, fail: bool = False, audit_hook=None) -> None:
        super().__init__(api_key="k", audit_hook=audit_hook)
        self.provider = provider
        self.fail = fail
        self.calls = 0

    async def _generate(self, req: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.fail:
            raise RuntimeError(f"{self.provider} boom")
        return LLMResponse(
            text=f"hi from {self.provider}",
            model=req.model or "?",
            provider=self.provider,
            usage=Usage(input_tokens=1, output_tokens=2),
            finish_reason="stop",
        )

    async def _embed(self, req: EmbedRequest) -> EmbedResponse:
        self.calls += 1
        if self.fail:
            raise RuntimeError(f"{self.provider} embed boom")
        return EmbedResponse(
            embeddings=[[0.1, 0.2] for _ in req.inputs],
            model=req.model or "?",
            provider=self.provider,
        )

    async def stream(self, req: LLMRequest) -> AsyncIterator[str]:
        self.calls += 1
        if self.fail:
            raise RuntimeError(f"{self.provider} stream boom")
        for tok in ["a", "b", "c"]:
            yield tok


def _req() -> LLMRequest:
    return LLMRequest(messages=[Message(role="user", content="hello")])


def test_candidate_order_from_config():
    router = Router(adapters={"anthropic": FakeAdapter("anthropic")}, routing=ROUTING)
    cands = router.candidates("reasoning")
    assert [c.provider for c in cands] == ["anthropic", "openai", "google"]


def test_available_candidates_skips_disabled_providers():
    # Only openai has an adapter -> anthropic/google are "disabled" (no key).
    router = Router(adapters={"openai": FakeAdapter("openai")}, routing=ROUTING)
    avail = router.available_candidates("reasoning")
    assert [c.provider for c in avail] == ["openai"]


async def test_generate_uses_first_available():
    a = FakeAdapter("anthropic")
    o = FakeAdapter("openai")
    router = Router(adapters={"anthropic": a, "openai": o}, routing=ROUTING)
    resp = await router.generate("reasoning", _req())
    assert resp.provider == "anthropic"
    assert a.calls == 1 and o.calls == 0


async def test_generate_falls_back_on_error():
    a = FakeAdapter("anthropic", fail=True)
    o = FakeAdapter("openai")
    router = Router(adapters={"anthropic": a, "openai": o}, routing=ROUTING)
    resp = await router.generate("reasoning", _req())
    assert resp.provider == "openai"  # fell back past the failing anthropic
    assert a.calls == 1 and o.calls == 1


async def test_generate_all_fail_raises_with_detail():
    a = FakeAdapter("anthropic", fail=True)
    o = FakeAdapter("openai", fail=True)
    router = Router(adapters={"anthropic": a, "openai": o}, routing=ROUTING)
    with pytest.raises(AllCandidatesFailed) as ei:
        await router.generate("reasoning", _req())
    assert len(ei.value.errors) == 2
    assert {p for p, _, _ in ei.value.errors} == {"anthropic", "openai"}


async def test_no_available_provider_raises():
    # google has an adapter but it's not a candidate before... actually it is;
    # use a task with only openai candidate and provide no openai adapter.
    router = Router(adapters={"anthropic": FakeAdapter("anthropic")}, routing=ROUTING)
    with pytest.raises(NoAvailableProvider):
        await router.embed("embeddings", EmbedRequest(inputs=["x"]))


async def test_default_model_is_config_only():
    """Switching the default model is a routing.yaml edit, not code."""
    a = FakeAdapter("anthropic")
    o = FakeAdapter("openai")
    adapters = {"anthropic": a, "openai": o}
    # default config -> anthropic wins
    r1 = Router(adapters=adapters, routing=ROUTING)
    assert (await r1.generate("reasoning", _req())).provider == "anthropic"
    # reorder candidates in config only -> openai now wins, no code change
    reordered = {
        **ROUTING,
        "task_types": {
            **ROUTING["task_types"],
            "reasoning": [
                {"provider": "openai", "model": "gpt-x"},
                {"provider": "anthropic", "model": "claude-x"},
            ],
        },
    }
    r2 = Router(adapters=adapters, routing=reordered)
    assert (await r2.generate("reasoning", _req())).provider == "openai"


async def test_audit_hook_fires_on_every_call():
    events: list[dict] = []

    async def hook(ev: dict) -> None:
        events.append(ev)

    a = FakeAdapter("anthropic", audit_hook=hook)
    router = Router(adapters={"anthropic": a}, routing=ROUTING)
    await router.generate("reasoning", _req())
    phases = [e["phase"] for e in events]
    assert "request" in phases and "response" in phases
    assert all(e["event_type"] == "model_call" for e in events)


async def test_audit_hook_records_errors():
    events: list[dict] = []

    async def hook(ev: dict) -> None:
        events.append(ev)

    a = FakeAdapter("anthropic", fail=True, audit_hook=hook)
    router = Router(adapters={"anthropic": a}, routing=ROUTING)
    with pytest.raises(AllCandidatesFailed):
        await router.generate("reasoning", _req())
    assert any(e["phase"] == "error" for e in events)  # errors are never hidden


async def test_stream_falls_back_before_first_token():
    a = FakeAdapter("anthropic", fail=True)
    o = FakeAdapter("openai")
    router = Router(adapters={"anthropic": a, "openai": o}, routing=ROUTING)
    out = [tok async for tok in router.stream("reasoning", _req())]
    assert out == ["a", "b", "c"]
