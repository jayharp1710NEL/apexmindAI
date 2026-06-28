"""Prove model-agnosticism: print a completion from every configured provider,
all through the same internal interface and adapter boundary.

Run from the backend/ directory so `app` is importable:

    cd backend && python ../scripts/prove_model_agnostic.py

Only providers whose API key is present in the environment will run; others are
reported as skipped. The point: identical calling code, different providers — no
vendor SDK touched outside app/router/adapters/.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make `app` importable whether run from repo root or backend/.
_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config import settings  # noqa: E402  (after sys.path bootstrap)
from app.router.router import build_adapters, load_routing_config  # noqa: E402
from app.router.types import LLMRequest, Message  # noqa: E402

PROMPT = "In one short sentence, say hello and name the company that made you."


def _model_for(provider: str, routing: dict) -> str | None:
    """Pick a reasonable model for a provider from routing.yaml (first match)."""
    for candidates in routing.get("task_types", {}).values():
        for c in candidates:
            if c["provider"] == provider:
                return c["model"]
    return None


async def main() -> int:
    routing_path = Path(settings.routing_config_path)
    if not routing_path.is_absolute():
        routing_path = _BACKEND / routing_path
    routing = load_routing_config(routing_path)
    adapters = build_adapters(settings)

    if not adapters:
        print("No providers configured. Set at least one *_API_KEY in your env.")
        return 1

    print(f"Configured providers: {', '.join(sorted(adapters))}\n")
    failures = 0
    for provider, adapter in adapters.items():
        model = _model_for(provider, routing)
        if model is None:
            print(f"[{provider}] no model in routing.yaml — skipped\n")
            continue
        req = LLMRequest(
            messages=[Message(role="user", content=PROMPT)],
            model=model,
            max_tokens=64,
            temperature=0.2,
        )
        print(f"[{provider}] model={model}")
        try:
            resp = await adapter.generate(req)
            print(f"  -> {resp.text.strip()}")
            print(
                f"  (tokens in/out: {resp.usage.input_tokens}/"
                f"{resp.usage.output_tokens})\n"
            )
        except Exception as exc:  # noqa: BLE001 — diagnostic script
            failures += 1
            print(f"  !! failed: {exc!r}\n")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
