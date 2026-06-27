"""Critic agent: self-evaluation of a draft answer.

Returns a strict-JSON scorecard {issues, hallucination_risk, confidence,
needs_revision}. `self_evaluate` revises the draft ONCE when the risk is high (or
the critic asks for a revision), then re-scores. The scorecard is attached to the
final message so every answer carries a real evaluation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel, Field

from app.orchestrator.planner import extract_json
from app.prompts.registry import get_active_prompt

Risk = Literal["low", "medium", "high"]


class Scorecard(BaseModel):
    issues: list[str] = Field(default_factory=list)
    hallucination_risk: Risk = "medium"
    confidence: float = 0.5
    needs_revision: bool = False
    revised: bool = False

    @property
    def is_high_risk(self) -> bool:
        return self.hallucination_risk == "high" or self.needs_revision


async def critique(
    llm, *, question: str, draft: str, sources: str = "", session_factory=None
) -> Scorecard:
    system = await get_active_prompt("critic", session_factory)
    src = f"\n\nSources (the only support for claims):\n{sources}" if sources else ""
    prompt = (
        f"Question:\n{question}\n\nDraft answer to evaluate:\n{draft}{src}\n\n"
        f"Return the scorecard JSON."
    )
    resp = await llm.generate("critique", prompt=prompt, system=system,
                              json_mode=True, max_tokens=400, temperature=0.0)
    try:
        data = extract_json(resp.text)
        return Scorecard.model_validate(data)
    except Exception:
        # Never fabricate confidence; fall back to a cautious card.
        return Scorecard(issues=["critic output unparseable"],
                         hallucination_risk="medium", confidence=0.4)


async def self_evaluate(
    llm,
    *,
    question: str,
    draft: str,
    sources: str = "",
    revise: Callable[[str, Scorecard], Awaitable[str]] | None = None,
    session_factory=None,
) -> tuple[str, Scorecard]:
    """Critique `draft`; if high risk and a `revise` fn is given, revise once and
    re-score. Returns (final_text, scorecard).
    """
    card = await critique(llm, question=question, draft=draft, sources=sources,
                          session_factory=session_factory)
    if card.is_high_risk and revise is not None:
        revised_text = await revise(draft, card)
        new_card = await critique(llm, question=question, draft=revised_text,
                                  sources=sources, session_factory=session_factory)
        new_card.revised = True
        return revised_text, new_card
    return draft, card
