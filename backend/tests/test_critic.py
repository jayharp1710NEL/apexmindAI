"""Critic self-evaluation tests (no DB, no network)."""

from __future__ import annotations

from app.agents.critic import Scorecard, critique, self_evaluate
from app.router.types import LLMResponse, Usage

LOW = '{"issues":[],"hallucination_risk":"low","confidence":0.9,"needs_revision":false}'
HIGH = '{"issues":["unsupported claim"],"hallucination_risk":"high","confidence":0.3,"needs_revision":true}'


class FakeCriticLLM:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = 0

    async def generate(self, task_type, **kw):
        p = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return LLMResponse(text=p, model="m", provider="fake", usage=Usage())


async def test_low_risk_no_revision():
    llm = FakeCriticLLM([LOW])
    revised_called = {"n": 0}

    async def revise(prev, card):
        revised_called["n"] += 1
        return "should not be used"

    final, card = await self_evaluate(llm, question="q", draft="draft answer",
                                      revise=revise)
    assert final == "draft answer"
    assert card.hallucination_risk == "low" and card.revised is False
    assert revised_called["n"] == 0


async def test_high_risk_revises_once():
    llm = FakeCriticLLM([HIGH, LOW])  # 1st critique high, re-critique low

    async def revise(prev, card):
        return "revised answer"

    final, card = await self_evaluate(llm, question="q", draft="bad draft",
                                      revise=revise)
    assert final == "revised answer"
    assert card.revised is True
    assert card.hallucination_risk == "low"  # re-scored after revision


async def test_unparseable_critic_falls_back():
    card = await critique(FakeCriticLLM(["not json"]), question="q", draft="d")
    assert isinstance(card, Scorecard)
    assert card.hallucination_risk == "medium"
    assert 0.0 <= card.confidence <= 1.0


async def test_high_risk_without_revise_keeps_draft():
    llm = FakeCriticLLM([HIGH])
    final, card = await self_evaluate(llm, question="q", draft="d", revise=None)
    assert final == "d" and card.revised is False and card.is_high_risk
