"""Seed tool_registry from the in-code BUILTIN_TOOL_LEVELS (idempotent).

Run from repo root or backend/:  python scripts/seed_tool_registry.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import select  # noqa: E402

from app.db.models import ToolRegistry  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402
from app.tools.registry import BUILTIN_TOOL_LEVELS  # noqa: E402

DESCRIPTIONS = {
    "web_search": "Keyless web search; returns untrusted DATA.",
    "web_fetch": "Fetch a URL as text; untrusted DATA.",
    "code_exec": "Run untrusted Python in the network-less sandbox.",
}


async def main() -> None:
    async with async_session_factory() as s, s.begin():
        for name, level in BUILTIN_TOOL_LEVELS.items():
            existing = await s.scalar(
                select(ToolRegistry).where(ToolRegistry.name == name)
            )
            if existing is None:
                s.add(ToolRegistry(name=name, level=level, enabled=True,
                                   description=DESCRIPTIONS.get(name)))
                print(f"registered tool '{name}' (L{level})")
            else:
                print(f"tool '{name}' already registered — skipped")


if __name__ == "__main__":
    asyncio.run(main())
