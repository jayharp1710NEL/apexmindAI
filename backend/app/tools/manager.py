"""Tool Manager — the single choke point for executing any tool.

Every dispatch runs the same safety sequence, in order:

  1. resolve the tool's required level (registry)
  2. check E-STOP
  3. permission engine decides ALLOW / NEEDS_APPROVAL / DENY
  4. if NEEDS_APPROVAL: block on a human approval (timeout = auto-deny)
  5. re-check E-STOP after approval (state may have changed while waiting)
  6. execute the tool implementation
  7. audit the call and persist a tool_results row

A tool implementation is only ever reached at step 6 — there is no path that runs a
tool before its decision is ALLOW (or an approved NEEDS_APPROVAL). This is the
property the Step-6 test pins down.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.safety.approvals import ApprovalRegistry
from app.safety.estop import EStop
from app.safety.permission_engine import PermissionDecision, PermissionEngine
from app.tools.registry import BUILTIN_TOOL_LEVELS
from app.tools.schema import ToolResult

logger = logging.getLogger(__name__)

ToolImpl = Callable[[dict], Awaitable[ToolResult]]


class ToolManager:
    def __init__(
        self,
        *,
        impls: dict[str, ToolImpl],
        estop: EStop,
        engine: PermissionEngine | None = None,
        approvals: ApprovalRegistry | None = None,
        registry: dict[str, int] | None = None,
        audit_logger=None,
        session_factory=None,
        approval_timeout: float = 300.0,
    ) -> None:
        self.impls = impls
        self.estop = estop
        self.engine = engine or PermissionEngine()
        self.approvals = approvals or ApprovalRegistry()
        self.registry = registry or dict(BUILTIN_TOOL_LEVELS)
        self.audit_logger = audit_logger
        self.session_factory = session_factory
        self.approval_timeout = approval_timeout

    async def dispatch(
        self,
        name: str,
        args: dict | None = None,
        *,
        session_id: str | None = None,
    ) -> ToolResult:
        args = args or {}
        level = self.registry.get(name)
        if level is None:
            return await self._finish(
                ToolResult(tool_name=name, level=-1, status="error",
                           error=f"unknown tool '{name}'"),
                session_id,
            )

        # 2-3: E-STOP + permission decision
        estop_engaged = await self.estop.is_engaged()
        result = self.engine.decide(level, estop_engaged=estop_engaged)

        if result.decision == PermissionDecision.DENY:
            return await self._finish(
                ToolResult(tool_name=name, level=level, status="denied",
                           reason=result.reason),
                session_id,
            )

        # 4: human approval for Level >=3
        if result.decision == PermissionDecision.NEEDS_APPROVAL:
            record = self.approvals.request(
                tool_name=name, level=level, session_id=session_id,
                detail={"args_keys": sorted(args.keys())},
            )
            await self._audit_decision(name, level, "needs_approval", session_id,
                                       {"approval_id": record.id})
            approved = await self.approvals.wait(record.id, self.approval_timeout)
            if not approved:
                return await self._finish(
                    ToolResult(tool_name=name, level=level, status="denied",
                               reason="approval denied or timed out"),
                    session_id,
                )
            # 5: re-check E-STOP — it may have been engaged during the wait
            if await self.estop.is_engaged():
                return await self._finish(
                    ToolResult(tool_name=name, level=level, status="denied",
                               reason="emergency stop engaged during approval"),
                    session_id,
                )

        # 6: execute
        impl = self.impls.get(name)
        if impl is None:
            return await self._finish(
                ToolResult(tool_name=name, level=level, status="error",
                           error=f"no implementation registered for '{name}'"),
                session_id,
            )
        try:
            exec_result = await impl(args)
        except Exception as exc:  # surface, never hide
            logger.exception("tool %s failed", name)
            return await self._finish(
                ToolResult(tool_name=name, level=level, status="error",
                           error=f"{type(exc).__name__}: {exc}"),
                session_id,
            )
        # Normalize identity fields so impls can't misreport themselves.
        exec_result.tool_name = name
        exec_result.level = level
        return await self._finish(exec_result, session_id)

    # -- audit + persistence --------------------------------------------- #
    async def _audit_decision(self, name, level, decision, session_id, detail):
        if self.audit_logger is not None:
            await self.audit_logger.log_tool_call(
                tool_name=name, level=level, decision=decision,
                session_id=session_id, detail=detail,
            )

    async def _finish(self, result: ToolResult, session_id: str | None) -> ToolResult:
        await self._audit_decision(
            result.tool_name, result.level, result.status, session_id,
            {"reason": result.reason} if result.reason else {},
        )
        await self._persist(result, session_id)
        return result

    async def _persist(self, result: ToolResult, session_id: str | None) -> None:
        if self.session_factory is None:
            return
        from app.db.models import ToolResult as ToolResultRow

        try:
            async with self.session_factory() as s, s.begin():
                s.add(
                    ToolResultRow(
                        step_id=None,
                        tool_name=result.tool_name,
                        level=max(result.level, 0),
                        status=result.status,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        return_code=result.return_code,
                        duration_ms=result.duration_ms,
                        result=result.result,
                    )
                )
        except Exception as exc:  # pragma: no cover - persistence best-effort
            logger.warning("failed to persist tool_result: %r", exc)
