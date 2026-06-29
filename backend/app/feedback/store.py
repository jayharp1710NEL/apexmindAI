"""Collect training examples from user feedback.

Every rating/correction is appended as one JSONL line to the training dataset. This
is the corpus you later fine-tune `apexmind` on — keeping its training data current,
relevant, and corrected. Storage is a plain JSONL file so it's easy to inspect,
version, and feed into a LoRA run (see scripts/export_training_data.py).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings

# backend/ root (parent of app/) so the dataset persists with the mounted volume.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _dataset_path() -> Path:
    d = Path(settings.training_data_dir)
    if not d.is_absolute():
        d = _BACKEND_ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return d / "feedback.jsonl"


def append_example(record: dict[str, Any]) -> dict:
    """Append one training example. Returns a small summary."""
    record = {"ts": datetime.now(UTC).isoformat(), **record}
    path = _dataset_path()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"saved": True, "path": str(path)}


def count_examples() -> int:
    path = _dataset_path()
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())
