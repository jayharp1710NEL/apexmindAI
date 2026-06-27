"""Prompt loading: prefer the active DB-stored version, fall back to the seed file.

System prompts are versioned in `prompt_versions` (seeded by scripts/seed_prompts.py).
Before seeding — and in DB-less tests — the on-disk seed is used.
"""

from __future__ import annotations

from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent / "seeds"


def load_seed(name: str) -> str:
    path = SEED_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"no seed prompt for '{name}' at {path}")
    return path.read_text()


async def get_active_prompt(name: str, session_factory=None) -> str:
    """Return the active prompt text for `name` (DB if available, else seed)."""
    if session_factory is not None:
        try:
            from sqlalchemy import select

            from app.db.models import PromptVersion

            async with session_factory() as s:
                row = await s.scalar(
                    select(PromptVersion)
                    .where(PromptVersion.name == name, PromptVersion.is_active.is_(True))
                    .order_by(PromptVersion.version.desc())
                )
            if row is not None:
                return row.content
        except Exception:
            pass  # fall back to seed
    return load_seed(name)
