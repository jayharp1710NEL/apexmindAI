"""Provider-agnostic request/response types for the LLM layer.

These are the ONLY shapes the application sees. Adapters translate between these
and each vendor SDK. Nothing here imports a vendor SDK.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMRequest(BaseModel):
    """A model-agnostic generation request.

    `model` is filled in by the router from routing.yaml; callers usually leave it
    unset and pass a task_type to the interface instead.
    """

    model: str | None = None
    messages: list[Message]
    system: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    stop: list[str] | None = None
    # When True, adapters instruct the provider to emit strict JSON (used by the
    # orchestrator/critic/safety/memory agents).
    json_mode: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    text: str
    model: str
    provider: str
    usage: Usage = Field(default_factory=Usage)
    finish_reason: str | None = None
    # Opaque provider payload for debugging/audit; never relied on by app logic.
    raw: dict[str, Any] | None = None


class EmbedRequest(BaseModel):
    model: str | None = None
    inputs: list[str]


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    provider: str
    usage: Usage = Field(default_factory=Usage)
