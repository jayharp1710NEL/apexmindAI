"""ToolManager safety tests.

The headline acceptance test: a Level-3 action does NOT execute without approval.
Also covers L2 auto-run, L5 refusal, E-STOP halting, approval-then-run, and the
re-check of E-STOP after approval.
"""

from __future__ import annotations

import asyncio

from app.safety.approvals import ApprovalRegistry
from app.safety.estop import EStop
from app.safety.permission_engine import PermissionEngine
from app.tools.manager import ToolManager
from app.tools.schema import ToolResult


class SpyTool:
    """Records whether it actually ran."""

    def __init__(self) -> None:
        self.ran = False

    async def __call__(self, args: dict) -> ToolResult:
        self.ran = True
        return ToolResult(tool_name="x", level=0, status="ok", stdout="executed")


def _manager(spy, *, level, estop=None, approvals=None, timeout=300.0):
    return ToolManager(
        impls={"spy": spy},
        estop=estop or EStop(),
        engine=PermissionEngine(max_level=4),
        approvals=approvals or ApprovalRegistry(),
        registry={"spy": level},
        approval_timeout=timeout,
    )


async def _resolve_when_pending(approvals: ApprovalRegistry, approved: bool):
    for _ in range(200):  # up to ~2s
        pend = approvals.pending()
        if pend:
            approvals.resolve(pend[0].id, approved)
            return pend[0].id
        await asyncio.sleep(0.01)
    raise AssertionError("no pending approval appeared")


async def test_level2_runs_without_approval():
    spy = SpyTool()
    mgr = _manager(spy, level=2)
    res = await mgr.dispatch("spy")
    assert res.status == "ok" and spy.ran is True


async def test_level3_does_not_execute_without_approval():
    """ACCEPTANCE: Level-3 action must not run unless a human approves it."""
    spy = SpyTool()
    # Short timeout, and nobody approves -> must auto-deny and never execute.
    mgr = _manager(spy, level=3, timeout=0.1)
    res = await mgr.dispatch("spy")
    assert res.status == "denied"
    assert spy.ran is False  # the tool body was never reached


async def test_level3_runs_after_human_approval():
    spy = SpyTool()
    approvals = ApprovalRegistry()
    mgr = _manager(spy, level=3, approvals=approvals, timeout=5.0)
    dispatch = asyncio.create_task(mgr.dispatch("spy"))
    await _resolve_when_pending(approvals, approved=True)
    res = await dispatch
    assert res.status == "ok" and spy.ran is True


async def test_level3_denied_when_human_rejects():
    spy = SpyTool()
    approvals = ApprovalRegistry()
    mgr = _manager(spy, level=3, approvals=approvals, timeout=5.0)
    dispatch = asyncio.create_task(mgr.dispatch("spy"))
    await _resolve_when_pending(approvals, approved=False)
    res = await dispatch
    assert res.status == "denied" and spy.ran is False


async def test_level5_always_refused():
    spy = SpyTool()
    mgr = _manager(spy, level=5)
    res = await mgr.dispatch("spy")
    assert res.status == "denied" and spy.ran is False
    assert "always refused" in (res.reason or "")


async def test_estop_blocks_execution():
    spy = SpyTool()
    estop = EStop()
    await estop.engage("halt")
    mgr = _manager(spy, level=2, estop=estop)
    res = await mgr.dispatch("spy")
    assert res.status == "denied" and spy.ran is False
    assert "emergency stop" in (res.reason or "")


async def test_estop_engaged_during_approval_blocks_run():
    spy = SpyTool()
    estop = EStop()
    approvals = ApprovalRegistry()
    mgr = _manager(spy, level=3, estop=estop, approvals=approvals, timeout=5.0)
    dispatch = asyncio.create_task(mgr.dispatch("spy"))

    # Approve, but engage E-STOP first so the post-approval re-check denies.
    for _ in range(200):
        pend = approvals.pending()
        if pend:
            await estop.engage("halt mid-approval")
            approvals.resolve(pend[0].id, True)
            break
        await asyncio.sleep(0.01)
    res = await dispatch
    assert res.status == "denied" and spy.ran is False
    assert "emergency stop" in (res.reason or "")


async def test_unknown_tool_errors():
    mgr = _manager(SpyTool(), level=2)
    res = await mgr.dispatch("does_not_exist")
    assert res.status == "error"
