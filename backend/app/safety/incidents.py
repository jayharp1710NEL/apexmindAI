"""Persist safety incidents (refusals, injection detections, E-STOP, etc.)."""

from __future__ import annotations

import uuid
from typing import Any

from app.db.models import SafetyIncident


async def log_incident(
    session_factory,
    *,
    kind: str,
    severity: str = "info",
    decision: str | None = None,
    session_id: uuid.UUID | str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    if session_factory is None:
        return
    sid = None
    if isinstance(session_id, uuid.UUID):
        sid = session_id
    elif session_id:
        try:
            sid = uuid.UUID(str(session_id))
        except ValueError:
            sid = None
    try:
        async with session_factory() as s, s.begin():
            s.add(SafetyIncident(kind=kind, severity=severity, decision=decision,
                                 session_id=sid, detail=detail))
    except Exception:
        pass  # incident logging is best-effort; never break the request
