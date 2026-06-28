"""Pure (no-DB) tests for the audit hash chain.

These exercise compute_entry_hash and verify_rows over in-memory AuditLog objects,
so they run anywhere. DB-backed behavior is covered in test_audit_integration.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.audit.logger import compute_entry_hash, verify_rows
from app.db.models import AuditLog

TS = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)


def _make_chain(payloads: list[dict]) -> list[AuditLog]:
    rows: list[AuditLog] = []
    prev: str | None = None
    for i, payload in enumerate(payloads, start=1):
        h = compute_entry_hash(
            prev_hash=prev,
            ts=TS,
            actor="anthropic",
            event_type="model_call",
            session_id=None,
            payload=payload,
        )
        row = AuditLog(
            id=i,
            ts=TS,
            actor="anthropic",
            event_type="model_call",
            session_id=None,
            payload=payload,
            prev_hash=prev,
            entry_hash=h,
        )
        rows.append(row)
        prev = h
    return rows


def test_hash_is_deterministic():
    a = compute_entry_hash(
        prev_hash=None, ts=TS, actor="x", event_type="model_call",
        session_id=None, payload={"k": 1},
    )
    b = compute_entry_hash(
        prev_hash=None, ts=TS, actor="x", event_type="model_call",
        session_id=None, payload={"k": 1},
    )
    assert a == b and len(a) == 64


def test_hash_changes_with_payload():
    a = compute_entry_hash(
        prev_hash=None, ts=TS, actor="x", event_type="model_call",
        session_id=None, payload={"k": 1},
    )
    b = compute_entry_hash(
        prev_hash=None, ts=TS, actor="x", event_type="model_call",
        session_id=None, payload={"k": 2},
    )
    assert a != b


def test_chain_verifies():
    rows = _make_chain([{"phase": "request"}, {"phase": "response"}, {"phase": "done"}])
    check = verify_rows(rows)
    assert check.ok and check.count == 3 and check.first_broken_id is None


def test_tamper_with_payload_is_detected():
    rows = _make_chain([{"phase": "request"}, {"phase": "response"}])
    # Mutate a payload AFTER hashing — entry_hash no longer matches contents.
    rows[0].payload = {"phase": "TAMPERED"}
    check = verify_rows(rows)
    assert not check.ok
    assert check.first_broken_id == 1
    assert "tamper" in (check.reason or "").lower() or "mismatch" in (check.reason or "")


def test_broken_link_is_detected():
    rows = _make_chain([{"phase": "a"}, {"phase": "b"}, {"phase": "c"}])
    # Cut the link: row 3 no longer points at row 2's entry_hash.
    rows[2].prev_hash = "0" * 64
    check = verify_rows(rows)
    assert not check.ok and check.first_broken_id == 3
