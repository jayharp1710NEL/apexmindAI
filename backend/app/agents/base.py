"""Agents as prompt + tool profiles over the shared models.

An AgentProfile binds a system prompt (versioned record name), a default routing
task_type, and a tool *ceiling* — the maximum permission level the agent may ever
request. The ceiling is advisory at planning time and enforced for real by the
permission engine at dispatch time.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    name: str
    prompt_name: str          # key into prompt_versions / seeds
    task_type: str            # routing task_type
    tool_ceiling: int         # max permission level this agent may request


PROFILES: dict[str, AgentProfile] = {
    # Research may use L1 web tools.
    "research": AgentProfile("research", "orchestrator", "reasoning", tool_ceiling=1),
    # Coding may use L2 sandboxed code execution.
    "coding": AgentProfile("coding", "orchestrator", "coding", tool_ceiling=2),
    # Critic/Safety/Memory are analysis-only: no tools.
    "critic": AgentProfile("critic", "critic", "critique", tool_ceiling=0),
    "safety": AgentProfile("safety", "safety", "structured_json", tool_ceiling=0),
    "memory": AgentProfile("memory", "memory", "structured_json", tool_ceiling=0),
}


def get_profile(name: str) -> AgentProfile | None:
    return PROFILES.get(name)
