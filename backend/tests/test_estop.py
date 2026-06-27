"""E-STOP in-memory behavior (no Redis required)."""

from __future__ import annotations

from app.safety.estop import EStop


async def test_estop_engage_clear_cycle():
    estop = EStop()  # in-memory
    assert await estop.is_engaged() is False
    await estop.engage("test")
    assert await estop.is_engaged() is True
    await estop.clear()
    assert await estop.is_engaged() is False
