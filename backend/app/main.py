"""ApexMind FastAPI application entrypoint.

Step 1 scaffold: exposes a health check only. The WebSocket chat endpoint,
orchestrator routes, and safety/audit wiring are added in later build steps.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="ApexMind AI", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
