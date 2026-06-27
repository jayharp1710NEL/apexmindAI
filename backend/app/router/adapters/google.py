"""Google (Gemini) adapter. Vendor SDK imported lazily, only here."""

from __future__ import annotations

from app.router.adapters.base import BaseAdapter
from app.router.types import EmbedRequest, EmbedResponse, LLMRequest, LLMResponse, Usage


class GoogleAdapter(BaseAdapter):
    provider = "google"

    def _configure(self):
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        return genai

    async def _generate(self, req: LLMRequest) -> LLMResponse:
        genai = self._configure()
        # Gemini takes system instruction separately; history is contents.
        contents = [
            {"role": "user" if m.role != "assistant" else "model", "parts": [m.content]}
            for m in req.messages
        ]
        system = req.system
        if req.json_mode:
            hint = "Respond with strict, valid JSON only. No prose, no code fences."
            system = f"{system}\n\n{hint}" if system else hint
        model = genai.GenerativeModel(req.model, system_instruction=system)
        gen_config: dict = {
            "max_output_tokens": req.max_tokens,
            "temperature": req.temperature,
        }
        if req.json_mode:
            gen_config["response_mime_type"] = "application/json"
        if req.stop:
            gen_config["stop_sequences"] = req.stop
        resp = await model.generate_content_async(
            contents, generation_config=gen_config
        )
        um = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=resp.text,
            model=req.model or "",
            provider=self.provider,
            usage=Usage(
                input_tokens=getattr(um, "prompt_token_count", 0) or 0,
                output_tokens=getattr(um, "candidates_token_count", 0) or 0,
            ),
            finish_reason="stop",
        )

    async def _embed(self, req: EmbedRequest) -> EmbedResponse:
        genai = self._configure()
        vectors: list[list[float]] = []
        for text in req.inputs:
            res = await genai.embed_content_async(model=req.model, content=text)
            vectors.append(res["embedding"])
        return EmbedResponse(
            embeddings=vectors, model=req.model or "", provider=self.provider
        )
