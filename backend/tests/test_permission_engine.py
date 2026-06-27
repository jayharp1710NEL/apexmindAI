"""Permission engine — exhaustive, pure decision tests."""

from __future__ import annotations

import pytest

from app.safety.permission_engine import PermissionDecision, PermissionEngine


@pytest.mark.parametrize("level", [0, 1, 2])
def test_low_levels_allow(level):
    res = PermissionEngine().decide(level, estop_engaged=False)
    assert res.decision == PermissionDecision.ALLOW


@pytest.mark.parametrize("level", [3, 4])
def test_mid_levels_need_approval(level):
    res = PermissionEngine().decide(level, estop_engaged=False)
    assert res.decision == PermissionDecision.NEEDS_APPROVAL


def test_level_5_always_denied():
    res = PermissionEngine().decide(5, estop_engaged=False)
    assert res.decision == PermissionDecision.DENY
    assert "always refused" in res.reason


def test_estop_denies_everything():
    eng = PermissionEngine()
    for level in range(0, 6):
        res = eng.decide(level, estop_engaged=True)
        assert res.decision == PermissionDecision.DENY
        assert "emergency stop" in res.reason


def test_invalid_levels_denied():
    eng = PermissionEngine()
    assert eng.decide(-1, estop_engaged=False).decision == PermissionDecision.DENY
    assert eng.decide(99, estop_engaged=False).decision == PermissionDecision.DENY


def test_ceiling_cannot_exceed_four():
    # Even if misconfigured to allow level 5, the engine clamps to 4 and refuses 5.
    eng = PermissionEngine(max_level=5)
    assert eng.max_level == 4
    assert eng.decide(5, estop_engaged=False).decision == PermissionDecision.DENY


def test_lower_ceiling_denies_above_it():
    eng = PermissionEngine(max_level=1)
    assert eng.decide(2, estop_engaged=False).decision == PermissionDecision.DENY
