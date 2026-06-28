"""Approval registry for Level >=3 tool actions.

A pending approval blocks the tool call on an asyncio.Event until a human resolves
it (via the safety API) or it times out — and a timeout is an automatic DENY, never
an implicit allow. This is what keeps the system under human control.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

ApprovalStatus = Literal["pending", "approved", "denied"]


@dataclass
class ApprovalRecord:
    id: str
    tool_name: str
    level: int
    session_id: str | None
    detail: dict[str, Any]
    status: ApprovalStatus = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ApprovalRegistry:
    def __init__(self) -> None:
        self._records: dict[str, ApprovalRecord] = {}
        self._events: dict[str, asyncio.Event] = {}

    def request(
        self,
        *,
        tool_name: str,
        level: int,
        session_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> ApprovalRecord:
        approval_id = str(uuid.uuid4())
        record = ApprovalRecord(
            id=approval_id,
            tool_name=tool_name,
            level=level,
            session_id=session_id,
            detail=detail or {},
        )
        self._records[approval_id] = record
        self._events[approval_id] = asyncio.Event()
        return record

    async def wait(self, approval_id: str, timeout: float) -> bool:
        """Block until resolved or timeout. Returns True only if approved.

        Timeout auto-denies — the safe default.
        """
        event = self._events[approval_id]
        try:
            await asyncio.wait_for(event.wait(), timeout)
        except TimeoutError:
            self._records[approval_id].status = "denied"
            return False
        return self._records[approval_id].status == "approved"

    def resolve(self, approval_id: str, approved: bool) -> bool:
        """Resolve a pending approval. Returns False if unknown/already resolved."""
        record = self._records.get(approval_id)
        if record is None or record.status != "pending":
            return False
        record.status = "approved" if approved else "denied"
        self._events[approval_id].set()
        return True

    def get(self, approval_id: str) -> ApprovalRecord | None:
        return self._records.get(approval_id)

    def pending(self) -> list[ApprovalRecord]:
        return [r for r in self._records.values() if r.status == "pending"]
