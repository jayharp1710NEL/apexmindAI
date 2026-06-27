"""OpenAI adapter (also the basis for the OpenAI-compatible/local adapter)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.router.adapters.base import BaseAdapter
from app.router.types import EmbedRequest, EmbedResponse, LLMRequest, LLMResponse, Usage


class OpenAIAdapter(BaseAdapter):
    provider = "openai"

    def _client(self):
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _build_messages(self, req: LLMRequest) -> list[dict]:
        msgs: list[dict] = []
        if req.system:
            msgs.append({"role": "system", "content": req.system})
        msgs.extend({"role": m.role, "content": m.content} for m in req.messages)
        return msgs

    async def _generate(self, req: LLMRequest) -> LLMResponse:
        client = self._client()
        kwargs: dict = {
            "model": req.model,
            "messages": self._build_messages(req),
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
        }
        if req.stop:
            kwargs["stop"] = req.stop
        if req.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        usage = resp.usage
        return LLMResponse(
            text=choice.message.content or "",
            model=resp.model,
            provider=self.provider,
            usage=Usage(
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            ),
            finish_reason=choice.finish_reason,
        )

    async def stream(self, req: LLMRequest) -> AsyncIterator[str]:
        client = self._client()
        kwargs: dict = {
            "model": req.model,
            "messages": self._build_messages(req),
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "stream": True,
        }
        if req.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        stream = await client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def _embed(self, req: EmbedRequest) -> EmbedResponse:
        client = self._client()
        resp = await client.embeddings.create(model=req.model, input=req.inputs)
        return EmbedResponse(
            embeddings=[d.embedding for d in resp.data],
            model=resp.model,
            provider=self.provider,
            usage=Usage(input_tokens=getattr(resp.usage, "prompt_tokens", 0) or 0),
        )


class OpenAICompatibleAdapter(OpenAIAdapter):
    """For local / self-hosted OpenAI-compatible servers (vLLM, Ollama, LM Studio).

    Identical wire format; only the base_url and (often dummy) key differ.
    """

    provider = "local"
