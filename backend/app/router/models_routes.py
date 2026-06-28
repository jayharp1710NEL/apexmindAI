"""List models the user can pick from in the UI.

For the local (Ollama / OpenAI-compatible) provider we query its /v1/models
endpoint so whatever you've `ollama pull`ed shows up. Cloud providers contribute a
small known set when their key is configured.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import settings

router = APIRouter(prefix="/api", tags=["models"])

_OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini"]


@router.get("/models")
async def list_models(request: Request) -> dict:
    models: list[dict] = []

    # Local provider (Ollama) — discover installed models.
    if settings.local_openai_base_url:
        try:
            import httpx

            base = settings.local_openai_base_url.rstrip("/")
            async with httpx.AsyncClient(timeout=5) as c:
                resp = await c.get(
                    f"{base}/models",
                    headers={"Authorization": f"Bearer {settings.local_openai_api_key or 'x'}"},
                )
            for m in resp.json().get("data", []):
                mid = m.get("id")
                if mid:
                    models.append({"id": mid, "provider": "local", "label": mid})
        except Exception:
            pass  # Ollama not reachable -> just omit local models

    # Cloud providers (only if a key is configured).
    if settings.openai_api_key:
        models += [{"id": m, "provider": "openai", "label": f"OpenAI · {m}"}
                   for m in _OPENAI_MODELS]

    return {"default_provider": settings.default_provider, "models": models}
