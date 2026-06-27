"""Append-only, hash-chained audit logger.

Every model call (and, from Step 6, every tool call) lands here. Each row links to
the previous one via a SHA-256 hash chain (`prev_hash` -> `entry_hash`), so any
tampering with an earlier row breaks verification of all later rows. The DB also
enforces append-only at the trigger level (UPDATE/DELETE rejected), so this is
defense in depth: the app cannot rewrite history, and altered rows are detectable.

The hash computation is a pure function (`compute_entry_hash`) so it is unit-testable
without a database. Appends are serialized with a Postgres advisory lock to keep the
chain linear under concurrency.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text

from app.db.models import AuditLog

# Arbitrary fixed key so all audit appends serialize against the same advisory lock.
_AUDIT_LOCK_KEY = 728041


def compute_entry_hash(
    *,
    prev_hash: str | None,
    ts: datetime,
    actor: str,
    event_type: str,
    session_id: uuid.UUID | str | None,
    payload: dict[str, Any],
) -> str:
    """Deterministic SHA-256 over the canonicalized row + the previous hash."""
    canonical = json.dumps(
        {
            "prev": prev_hash or "",
            "ts": ts.astimezone(timezone.utc).isoformat(),
            "actor": actor,
            "event_type": event_type,
            "session_id": str(session_id) if session_id else "",
            "payload": payload,
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class ChainCheck:
    ok: bool
    count: int
    first_broken_id: int | None = None
    reason: str | None = None


def verify_rows(rows: list[AuditLog]) -> ChainCheck:
    """Verify a list of audit rows ordered by ascending id.

    Checks both that each row's `prev_hash` matches the previous row's
    `entry_hash` and that each `entry_hash` recomputes from the row's contents.
    """
    prev: str | None = None
    for row in rows:
        if row.prev_hash != prev:
            return ChainCheck(False, len(rows), row.id, "broken link to previous row")
        recomputed = compute_entry_hash(
            prev_hash=row.prev_hash,
            ts=row.ts,
            actor=row.actor,
            event_type=row.event_type,
            session_id=row.session_id,
            payload=row.payload,
        )
        if recomputed != row.entry_hash:
            return ChainCheck(False, len(rows), row.id, "entry_hash mismatch (tampered)")
        prev = row.entry_hash
    return ChainCheck(True, len(rows))


class AuditLogger:
    def __init__(self, session_factory) -> None:
        # session_factory: async_sessionmaker producing AsyncSession
        self._session_factory = session_factory

    async def append(
        self,
        *,
        actor: str,
        event_type: str,
        payload: dict[str, Any],
        session_id: uuid.UUID | str | None = None,
    ) -> str:
        """Append one audit row and return its entry_hash."""
        async with self._session_factory() as session:
            async with session.begin():
                # Serialize appends so the chain stays linear under concurrency.
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:k)"), {"k": _AUDIT_LOCK_KEY}
                )
                prev_hash = await session.scalar(
                    select(AuditLog.entry_hash).order_by(AuditLog.id.desc()).limit(1)
                )
                ts = datetime.now(timezone.utc)
                entry_hash = compute_entry_hash(
                    prev_hash=prev_hash,
                    ts=ts,
                    actor=actor,
                    event_type=event_type,
                    session_id=session_id,
                    payload=payload,
                )
                session.add(
                    AuditLog(
                        ts=ts,
                        actor=actor,
                        event_type=event_type,
                        session_id=session_id
                        if isinstance(session_id, uuid.UUID)
                        else (uuid.UUID(session_id) if session_id else None),
                        payload=payload,
                        prev_hash=prev_hash,
                        entry_hash=entry_hash,
                    )
                )
            return entry_hash

    async def verify(self) -> ChainCheck:
        """Load the whole chain and verify it (used by tests / admin checks)."""
        async with self._session_factory() as session:
            rows = list(
                (await session.scalars(select(AuditLog).order_by(AuditLog.id.asc()))).all()
            )
        return verify_rows(rows)

    # -- hook factories --------------------------------------------------- #
    def model_audit_hook(self):
        """Return an async hook for BaseAdapter: logs every model call event."""

        async def _hook(event: dict[str, Any]) -> None:
            actor = event.get("provider", "model")
            event_type = event.get("event_type", "model_call")
            session_id = event.get("session_id")
            await self.append(
                actor=actor,
                event_type=event_type,
                payload=event,
                session_id=session_id,
            )

        return _hook

    async def log_tool_call(
        self,
        *,
        tool_name: str,
        level: int,
        decision: str,
        session_id: uuid.UUID | str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        """Convenience used by the Tool Manager in Step 6."""
        return await self.append(
            actor="tool",
            event_type="tool_call",
            payload={
                "tool_name": tool_name,
                "level": level,
                "decision": decision,
                **(detail or {}),
            },
            session_id=session_id,
        )
