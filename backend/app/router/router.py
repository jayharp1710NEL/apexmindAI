"""The router: maps a task_type to ordered model candidates and executes with
fallback.

Switching the default model is a routing.yaml change only — the router never
hard-codes a provider. Providers without a configured API key are skipped, and on
any adapter error the router falls back to the next candidate.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.router.adapters.base import AuditHook, BaseAdapter
from app.router.types import (
    EmbedRequest,
    EmbedResponse,
    LLMRequest,
    LLMResponse,
)

logger = logging.getLogger(__name__)


class RouterError(Exception):
    """Base class for routing failures."""


class NoAvailableProvider(RouterError):
    """No candidate for the task type has a configured/enabled adapter."""


class AllCandidatesFailed(RouterError):
    """Every candidate adapter raised; carries the collected errors."""

    def __init__(self, task_type: str, errors: list[tuple[str, str, str]]) -> None:
        self.task_type = task_type
        self.errors = errors  # (provider, model, repr(exc))
        detail = "; ".join(f"{p}/{m}: {e}" for p, m, e in errors)
        super().__init__(f"all candidates failed for '{task_type}': {detail}")


@dataclass(frozen=True)
class Candidate:
    provider: str
    model: str


def load_routing_config(path: str | Path) -> dict[str, Any]:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if "task_types" not in cfg:
        raise RouterError(f"routing config {path} missing 'task_types'")
    return cfg


class Router:
    def __init__(
        self,
        adapters: dict[str, BaseAdapter],
        routing: dict[str, Any],
    ) -> None:
        #: provider name -> adapter (only providers that are actually enabled)
        self.adapters = adapters
        self.routing = routing
        self.default_provider: str | None = routing.get("default_provider")

    # -- candidate resolution -------------------------------------------- #
    def candidates(self, task_type: str) -> list[Candidate]:
        raw = self.routing.get("task_types", {}).get(task_type)
        if not raw:
            raise RouterError(f"unknown task_type '{task_type}' in routing config")
        return [Candidate(provider=c["provider"], model=c["model"]) for c in raw]

    def available_candidates(self, task_type: str) -> list[Candidate]:
        """Candidates whose provider has an enabled adapter, order preserved."""
        return [c for c in self.candidates(task_type) if c.provider in self.adapters]

    # -- execution with fallback ----------------------------------------- #
    async def generate(self, task_type: str, req: LLMRequest) -> LLMResponse:
        cands = self.available_candidates(task_type)
        if not cands:
            raise NoAvailableProvider(
                f"no enabled provider for task_type '{task_type}'"
            )
        errors: list[tuple[str, str, str]] = []
        for cand in cands:
            adapter = self.adapters[cand.provider]
            call = req.model_copy(update={"model": cand.model})
            try:
                return await adapter.generate(call)
            except Exception as exc:  # fall back to next candidate
                logger.warning(
                    "generate failed on %s/%s: %r; falling back",
                    cand.provider, cand.model, exc,
                )
                errors.append((cand.provider, cand.model, repr(exc)))
        raise AllCandidatesFailed(task_type, errors)

    async def embed(self, task_type: str, req: EmbedRequest) -> EmbedResponse:
        cands = self.available_candidates(task_type)
        if not cands:
            raise NoAvailableProvider(
                f"no enabled provider for task_type '{task_type}'"
            )
        errors: list[tuple[str, str, str]] = []
        for cand in cands:
            adapter = self.adapters[cand.provider]
            call = req.model_copy(update={"model": cand.model})
            try:
                return await adapter.embed(call)
            except Exception as exc:
                logger.warning(
                    "embed failed on %s/%s: %r; falling back",
                    cand.provider, cand.model, exc,
                )
                errors.append((cand.provider, cand.model, repr(exc)))
        raise AllCandidatesFailed(task_type, errors)

    async def stream(self, task_type: str, req: LLMRequest) -> AsyncIterator[str]:
        """Stream from the first available candidate.

        Fallback applies only to the initial connection: if a provider fails before
        yielding any token we try the next, but once tokens start flowing we do not
        switch providers mid-stream.
        """
        cands = self.available_candidates(task_type)
        if not cands:
            raise NoAvailableProvider(
                f"no enabled provider for task_type '{task_type}'"
            )
        errors: list[tuple[str, str, str]] = []
        for cand in cands:
            adapter = self.adapters[cand.provider]
            call = req.model_copy(update={"model": cand.model})
            try:
                agen = adapter.stream(call)
                first = await agen.__anext__()
            except StopAsyncIteration:
                return
            except Exception as exc:
                logger.warning(
                    "stream failed to start on %s/%s: %r; falling back",
                    cand.provider, cand.model, exc,
                )
                errors.append((cand.provider, cand.model, repr(exc)))
                continue
            yield first
            async for delta in agen:
                yield delta
            return
        raise AllCandidatesFailed(task_type, errors)


# --------------------------------------------------------------------------- #
# Adapter factory: build the enabled adapter set from settings.
# --------------------------------------------------------------------------- #
def build_adapters(settings, audit_hook: AuditHook | None = None) -> dict[str, BaseAdapter]:
    """Construct adapters only for providers that have credentials configured.

    This is what makes 'provider disabled when no key' work end-to-end: a provider
    absent from this dict is simply skipped by the router.
    """
    from app.router.adapters.anthropic import AnthropicAdapter
    from app.router.adapters.google import GoogleAdapter
    from app.router.adapters.openai import OpenAIAdapter, OpenAICompatibleAdapter

    adapters: dict[str, BaseAdapter] = {}
    if settings.anthropic_api_key:
        adapters["anthropic"] = AnthropicAdapter(
            api_key=settings.anthropic_api_key, audit_hook=audit_hook
        )
    if settings.openai_api_key:
        adapters["openai"] = OpenAIAdapter(
            api_key=settings.openai_api_key, audit_hook=audit_hook
        )
    if settings.google_api_key:
        adapters["google"] = GoogleAdapter(
            api_key=settings.google_api_key, audit_hook=audit_hook
        )
    if settings.local_openai_base_url:
        adapters["local"] = OpenAICompatibleAdapter(
            api_key=settings.local_openai_api_key or "not-needed",
            base_url=settings.local_openai_base_url,
            audit_hook=audit_hook,
        )
    return adapters
