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


def create_app(*, llm=None, session_factory=None) -> FastAPI:
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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(chat_router)
    return app


app = create_app()
