"""Permission engine — the gate every tool call passes through.

Pure decision logic (no I/O), so it is exhaustively unit-testable. The caller
(ToolManager) supplies the current E-STOP state; the engine maps a tool's required
permission level to one of three decisions:

    Levels 0-2  -> ALLOW            (subject to E-STOP)
    Levels 3-4  -> NEEDS_APPROVAL   (explicit human approval required)
    Level  5    -> DENY             (always refused)
    E-STOP on   -> DENY             (everything halts)

`max_level` (default 4, from settings.max_tool_level) is a hard ceiling: anything
above it is denied. Level 5 is therefore always refused even if max_level changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    NEEDS_APPROVAL = "needs_approval"
    DENY = "deny"


@dataclass(frozen=True)
class PermissionResult:
    decision: PermissionDecision
    level: int
    reason: str


# The two highest levels are gated behind human approval.
_APPROVAL_FLOOR = 3
# Level 5 is the absolute refusal line regardless of configuration.
ALWAYS_REFUSED_LEVEL = 5


class PermissionEngine:
    def __init__(self, max_level: int = 4) -> None:
        # max_level cannot exceed 4 — Level 5 is always refused.
        self.max_level = min(max_level, ALWAYS_REFUSED_LEVEL - 1)

    def decide(self, level: int, *, estop_engaged: bool) -> PermissionResult:
        if estop_engaged:
            return PermissionResult(
                PermissionDecision.DENY, level, "emergency stop is engaged"
            )
        if level < 0 or level > ALWAYS_REFUSED_LEVEL:
            return PermissionResult(
                PermissionDecision.DENY, level, f"invalid permission level {level}"
            )
        if level >= ALWAYS_REFUSED_LEVEL:
            return PermissionResult(
                PermissionDecision.DENY, level,
                "Level 5 actions are always refused",
            )
        if level > self.max_level:
            return PermissionResult(
                PermissionDecision.DENY, level,
                f"level {level} exceeds the configured ceiling {self.max_level}",
            )
        if level >= _APPROVAL_FLOOR:
            return PermissionResult(
                PermissionDecision.NEEDS_APPROVAL, level,
                f"level {level} requires explicit human approval",
            )
        return PermissionResult(PermissionDecision.ALLOW, level, "permitted")
