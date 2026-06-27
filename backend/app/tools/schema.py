"""Tool call / result schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool_name: str
    level: int
    # ok | denied | error | timeout
    status: str
    stdout: str | None = None
    stderr: str | None = None
    return_code: int | None = None
    duration_ms: int | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    # populated when the call was gated (denied / needs-approval-then-denied)
    reason: str | None = None
