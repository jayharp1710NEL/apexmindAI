"""Run budget: caps a run by steps, wall-clock time, and (best-effort) cost.

Step and time limits are hard. Cost is estimated from token usage via a small price
table; unknown models price at 0 so cost never falsely halts a run, but known models
contribute to the USD ceiling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.router.types import Usage

# USD per 1K tokens (input, output). Rough, for budgeting only — not billing.
_PRICE_PER_1K: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (0.015, 0.075),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4-5-20251001": (0.0008, 0.004),
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
}


def estimate_cost(model: str | None, usage: Usage) -> float:
    if not model:
        return 0.0
    inp, out = _PRICE_PER_1K.get(model, (0.0, 0.0))
    return (usage.input_tokens / 1000) * inp + (usage.output_tokens / 1000) * out


@dataclass
class Budget:
    max_steps: int
    max_seconds: float
    max_cost_usd: float
    started_at: float = field(default_factory=time.monotonic)
    steps_used: int = 0
    cost_usd: float = 0.0

    @classmethod
    def from_settings(cls, settings) -> Budget:
        return cls(
            max_steps=settings.max_steps,
            max_seconds=float(settings.max_run_seconds),
            max_cost_usd=float(settings.max_run_cost_usd),
        )

    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    def tick_step(self) -> None:
        self.steps_used += 1

    def add_cost(self, model: str | None, usage: Usage) -> None:
        self.cost_usd += estimate_cost(model, usage)

    def check(self) -> tuple[bool, str | None]:
        """Return (ok, reason). ok=False means the run must halt now."""
        if self.steps_used >= self.max_steps:
            return False, f"step budget reached ({self.max_steps})"
        if self.elapsed() >= self.max_seconds:
            return False, f"time budget reached ({self.max_seconds:.0f}s)"
        if self.cost_usd >= self.max_cost_usd:
            return False, f"cost budget reached (${self.max_cost_usd:.2f})"
        return True, None
