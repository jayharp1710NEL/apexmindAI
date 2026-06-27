"""BaseAdapter — the single vendor boundary.

Every provider adapter subclasses this. No code outside this package
(`app/router/adapters/`) may import a vendor SDK.

`generate()` and `embed()` are template methods: they call the abstract
`_generate()` / `_embed()` and wrap them with an audit hook. The hook is a no-op
until Step 4 attaches a real sink, which guarantees that *every* model call is
auditable from the first call — there is no code path that reaches a provider
without passing through this wrapper.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.router.types import EmbedRequest, EmbedResponse, LLMRequest, LLMResponse

# An audit hook receives a structured event dict. Step 4 sets a real implementation
# (writing to the append-only audit_log). Until then it is None (no-op).
AuditHook = Callable[[dict[str, Any]], Awaitable[None]]


class BaseAdapter(ABC):
    #: short provider identifier, e.g. "anthropic", matches routing.yaml
    provider: str = "base"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        audit_hook: AuditHook | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self._audit_hook = audit_hook

    # -- audit seam ------------------------------------------------------- #
    async def _emit_audit(self, event: dict[str, Any]) -> None:
        if self._audit_hook is not None:
            await self._audit_hook(event)

    # -- public template methods (audited) -------------------------------- #
    async def generate(self, req: LLMRequest) -> LLMResponse:
        started = time.monotonic()
        await self._emit_audit(
            {
                "event_type": "model_call",
                "phase": "request",
                "provider": self.provider,
                "model": req.model,
                "kind": "generate",
                "message_count": len(req.messages),
                "json_mode": req.json_mode,
            }
        )
        try:
            resp = await self._generate(req)
        except Exception as exc:  # audit failures too — never hide errors
            await self._emit_audit(
                {
                    "event_type": "model_call",
                    "phase": "error",
                    "provider": self.provider,
                    "model": req.model,
                    "kind": "generate",
                    "error": repr(exc),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
            )
            raise
        await self._emit_audit(
            {
                "event_type": "model_call",
                "phase": "response",
                "provider": self.provider,
                "model": resp.model,
                "kind": "generate",
                "usage": resp.usage.model_dump(),
                "finish_reason": resp.finish_reason,
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        )
        return resp

    async def embed(self, req: EmbedRequest) -> EmbedResponse:
        started = time.monotonic()
        await self._emit_audit(
            {
                "event_type": "model_call",
                "phase": "request",
                "provider": self.provider,
                "model": req.model,
                "kind": "embed",
                "input_count": len(req.inputs),
            }
        )
        try:
            resp = await self._embed(req)
        except Exception as exc:
            await self._emit_audit(
                {
                    "event_type": "model_call",
                    "phase": "error",
                    "provider": self.provider,
                    "model": req.model,
                    "kind": "embed",
                    "error": repr(exc),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
            )
            raise
        await self._emit_audit(
            {
                "event_type": "model_call",
                "phase": "response",
                "provider": self.provider,
                "model": resp.model,
                "kind": "embed",
                "usage": resp.usage.model_dump(),
                "vector_count": len(resp.embeddings),
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        )
        return resp

    async def stream(self, req: LLMRequest) -> AsyncIterator[str]:
        """Yield text deltas. Default: fall back to a single non-streamed chunk."""
        resp = await self.generate(req)
        yield resp.text

    # -- provider-specific implementations -------------------------------- #
    @abstractmethod
    async def _generate(self, req: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    async def _embed(self, req: EmbedRequest) -> EmbedResponse: ...
