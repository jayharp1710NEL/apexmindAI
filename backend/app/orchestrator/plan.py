"""Plan schema produced by the orchestrator planner (strict JSON)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["research", "coding", "critic", "safety", "memory", "none"]
ToolName = Literal["code_exec", "web_search", "web_fetch", "none"]


class PlanStep(BaseModel):
    id: int
    description: str
    agent: AgentName = "none"
    tool: ToolName = "none"
    tool_level: int = 0
    # Optional concrete input for the tool: python code (code_exec), a query
    # (web_search), or a URL (web_fetch). May be empty — the orchestrator will
    # derive it (e.g. ask the coding agent to write code) when needed.
    tool_input: str = ""
    expected_output: str = ""
    # IDs of steps that must finish first. Steps with no (unmet) deps run in
    # parallel — this is how the boss uses several specialists at the same time.
    depends_on: list[int] = Field(default_factory=list)


class Plan(BaseModel):
    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    estimated_steps: int = 0

    @classmethod
    def single(cls, goal: str) -> Plan:
        """Trivial one-step plan for simple goals (direct answer)."""
        return cls(
            goal=goal,
            steps=[PlanStep(id=1, description=goal, agent="none", tool="none")],
            estimated_steps=1,
        )
