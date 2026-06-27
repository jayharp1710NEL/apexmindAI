"""Anthropic adapter. The vendor SDK is imported lazily, only here."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.router.adapters.base import BaseAdapter
from app.router.types import EmbedRequest, EmbedResponse, LLMRequest, LLMResponse, Usage


class AnthropicAdapter(BaseAdapter):
    provider = "anthropic"

    def _client(self):  # lazy import keeps the SDK out of import-time
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=self.api_key)

    def _build_kwargs(self, req: LLMRequest) -> dict:
        msgs = [{"role": m.role, "content": m.content} for m in req.messages]
        kwargs: dict = {
            "model": req.model,
            "messages": msgs,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
        }
        # Anthropic takes system as a top-level param, not a message.
        system = req.system
        if req.json_mode:
            hint = "Respond with strict, valid JSON only. No prose, no code fences."
            system = f"{system}\n\n{hint}" if system else hint
        if system:
            kwargs["system"] = system
        if req.stop:
            kwargs["stop_sequences"] = req.stop
        return kwargs

    async def _generate(self, req: LLMRequest) -> LLMResponse:
        client = self._client()
        msg = await client.messages.create(**self._build_kwargs(req))
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", None) == "text"
        )
        return LLMResponse(
            text=text,
            model=msg.model,
            provider=self.provider,
            usage=Usage(
                input_tokens=msg.usage.input_tokens,
                output_tokens=msg.usage.output_tokens,
            ),
            finish_reason=msg.stop_reason,
        )

    async def stream(self, req: LLMRequest) -> AsyncIterator[str]:
        client = self._client()
        async with client.messages.stream(**self._build_kwargs(req)) as stream:
            async for delta in stream.text_stream:
                yield delta

    async def _embed(self, req: EmbedRequest) -> EmbedResponse:
        # Anthropic does not provide an embeddings endpoint; routing.yaml sends
        # embeddings to providers that do (OpenAI / Google).
        raise NotImplementedError("Anthropic adapter does not support embeddings")
