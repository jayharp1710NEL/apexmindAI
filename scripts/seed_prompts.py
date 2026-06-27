"""Seed prompt_versions from app/prompts/seeds/*.md (idempotent).

Run from repo root or backend/:  python scripts/seed_prompts.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import select  # noqa: E402

from app.db.models import PromptVersion  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402
from app.prompts.registry import SEED_DIR  # noqa: E402

NAMES = ["orchestrator", "critic", "safety", "memory"]


async def main() -> None:
    async with async_session_factory() as s, s.begin():
        for name in NAMES:
            content = (SEED_DIR / f"{name}.md").read_text()
            existing = await s.scalar(
                select(PromptVersion).where(
                    PromptVersion.name == name, PromptVersion.version == 1
                )
            )
            if existing is None:
                s.add(PromptVersion(name=name, version=1, content=content,
                                    is_active=True))
                print(f"seeded prompt '{name}' v1")
            else:
                print(f"prompt '{name}' v1 already present — skipped")


if __name__ == "__main__":
    asyncio.run(main())
