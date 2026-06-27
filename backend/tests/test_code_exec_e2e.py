"""End-to-end: ToolManager dispatches code_exec (L2) into the real sandbox and
gets real stdout back — no approval needed at L2, and E-STOP halts it.
"""

from __future__ import annotations

from app.safety.estop import EStop
from app.safety.permission_engine import PermissionEngine
from app.tools.impl.code_exec import make_local_code_exec
from app.tools.manager import ToolManager


def _manager(estop=None):
    return ToolManager(
        impls={"code_exec": make_local_code_exec()},
        estop=estop or EStop(),
        engine=PermissionEngine(max_level=4),
        registry={"code_exec": 2},
    )


async def test_code_exec_real_output():
    res = await _manager().dispatch(
        "code_exec", {"code": "print('sandbox says hi'); print(6 * 7)"}
    )
    assert res.status == "ok"
    assert "sandbox says hi" in res.stdout
    assert "42" in res.stdout


async def test_code_exec_blocked_by_estop():
    estop = EStop()
    await estop.engage("halt")
    res = await _manager(estop).dispatch("code_exec", {"code": "print('should not run')"})
    assert res.status == "denied"
    assert "should not run" not in (res.stdout or "")
