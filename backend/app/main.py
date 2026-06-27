"""ApexMind FastAPI application entrypoint.

Wires the LLM interface and DB session factory onto `app.state` (so routes and
tests can read/override them), enables CORS for the local frontend, and mounts the
chat REST + WebSocket routes.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.chat.routes import router as chat_router
from app.config import settings
from app.safety.routes import router as safety_router


def create_app(
    *, llm=None, session_factory=None, estop=None, approvals=None, tool_manager=None
) -> FastAPI:
    app = FastAPI(title="ApexMind AI", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten for non-dev environments
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- shared state (overridable in tests) ---
    if session_factory is None:
        from app.db.session import async_session_factory

        session_factory = async_session_factory
    app.state.session_factory = session_factory

    if llm is None:
        from app.router.interface import LLMInterface

        llm = LLMInterface.from_settings()
    app.state.llm = llm

    # --- safety core ---
    if estop is None:
        from app.safety.estop import EStop

        estop = EStop.from_settings(settings)
    app.state.estop = estop

    if approvals is None:
        from app.safety.approvals import ApprovalRegistry

        approvals = ApprovalRegistry()
    app.state.approvals = approvals

    if tool_manager is None:
        from app.audit.logger import AuditLogger
        from app.safety.permission_engine import PermissionEngine
        from app.tools.impl.code_exec import make_local_code_exec
        from app.tools.manager import ToolManager

        tool_manager = ToolManager(
            impls={"code_exec": make_local_code_exec()},
            estop=estop,
            engine=PermissionEngine(max_level=settings.max_tool_level),
            approvals=approvals,
            audit_logger=AuditLogger(session_factory),
            session_factory=session_factory,
            approval_timeout=settings.approval_timeout_seconds,
        )
    app.state.tool_manager = tool_manager

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(chat_router)
    app.include_router(safety_router)
    return app


app = create_app()
