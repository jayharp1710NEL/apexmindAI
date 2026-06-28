"""LLMInterface — the single entry point the application uses for model calls.

The rest of the codebase calls `llm.generate(task_type=...)` / `llm.embed(...)` and
never touches an adapter or vendor SDK directly. The interface owns a Router, which
selects the concrete model from routing.yaml. Default-model changes are config-only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from app.config import settings as default_settings
from app.router.adapters.base import AuditHook
from app.router.router import Router, build_adapters, load_routing_config
from app.router.types import (
    EmbedRequest,
    EmbedResponse,
    LLMRequest,
    LLMResponse,
    Message,
)


class LLMInterface:
    def __init__(self, router: Router, embedding_task_type: str = "embeddings") -> None:
        self._router = router
        self._embedding_task_type = embedding_task_type

    # -- construction ----------------------------------------------------- #
    @classmethod
    def from_settings(
        cls,
        settings=default_settings,
        audit_hook: AuditHook | None = None,
        *,
        enable_default_audit: bool = True,
    ) -> LLMInterface:
        """Build the interface from settings.

        If no `audit_hook` is supplied and `enable_default_audit` is True (the
        production default), a hash-chained AuditLogger over the app DB session
        factory is attached, so EVERY model call is logged from the first call.
        Tests that have no database pass `enable_default_audit=False`.
        """
        routing_path = Path(settings.routing_config_path)
        if not routing_path.is_absolute():
            # resolve relative to the backend root (parent of app/)
            routing_path = Path(__file__).resolve().parents[2] / routing_path
        routing = load_routing_config(routing_path)

        if audit_hook is None and enable_default_audit:
            from app.audit.logger import AuditLogger
            from app.db.session import async_session_factory

            audit_hook = AuditLogger(async_session_factory).model_audit_hook()

        adapters = build_adapters(settings, audit_hook=audit_hook)
        return cls(
            Router(adapters=adapters, routing=routing),
            embedding_task_type=settings.embedding_task_type,
        )

    # -- generation ------------------------------------------------------- #
    async def generate(
        self,
        task_type: str,
        messages: list[Message] | None = None,
        *,
        prompt: str | None = None,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        json_mode: bool = False,
        stop: list[str] | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        req = LLMRequest(
            messages=messages or [Message(role="user", content=prompt or "")],
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
            stop=stop,
        )
        adapter = self._override_adapter(provider, model)
        if adapter is not None:
            return await adapter.generate(req.model_copy(update={"model": model}))
        return await self._router.generate(task_type, req)

    async def stream(
        self,
        task_type: str,
        messages: list[Message] | None = None,
        *,
        prompt: str | None = None,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        json_mode: bool = False,
        model: str | None = None,
        provider: str | None = None,
    ) -> AsyncIterator[str]:
        req = LLMRequest(
            messages=messages or [Message(role="user", content=prompt or "")],
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
        )
        # Explicit model override (from the UI picker) bypasses routing but still
        # goes through the adapter (so it is audited like any other call).
        adapter = self._override_adapter(provider, model)
        if adapter is not None:
            async for delta in adapter.stream(req.model_copy(update={"model": model})):
                yield delta
            return
        async for delta in self._router.stream(task_type, req):
            yield delta

    # -- helpers ---------------------------------------------------------- #
    def _override_adapter(self, provider: str | None, model: str | None):
        if not provider or not model:
            return None
        return self._router.adapters.get(provider)

    def available_providers(self) -> list[str]:
        return sorted(self._router.adapters.keys())

    # -- embeddings ------------------------------------------------------- #
    async def embed(
        self, inputs: list[str], *, task_type: str | None = None
    ) -> EmbedResponse:
        req = EmbedRequest(inputs=inputs)
        return await self._router.embed(task_type or self._embedding_task_type, req)
