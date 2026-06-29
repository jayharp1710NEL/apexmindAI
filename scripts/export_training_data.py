"""Export collected feedback into a clean instruction-tuning dataset.

Reads backend/datasets/training/feedback.jsonl and writes train.jsonl in the
chat-messages format most LoRA/QLoRA tools accept:
  {"messages":[{"role":"user",...},{"role":"assistant",...}]}

Usage (from repo root):  python scripts/export_training_data.py
Then fine-tune apexmind on train.jsonl (see model/README.md).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
DATA = _BACKEND / "datasets" / "training"
SRC = DATA / "feedback.jsonl"
OUT = DATA / "train.jsonl"


def main() -> int:
    if not SRC.exists():
        print(f"No feedback yet at {SRC}. Rate some answers in the app first.")
        return 1
    kept = 0
    seen: set[str] = set()
    with open(SRC, encoding="utf-8") as fin, open(OUT, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            msgs = rec.get("messages")
            if not msgs or len(msgs) < 2:
                continue
            key = json.dumps(msgs, sort_keys=True)
            if key in seen:  # de-dupe
                continue
            seen.add(key)
            fout.write(json.dumps({"messages": msgs}, ensure_ascii=False) + "\n")
            kept += 1
    print(f"Wrote {kept} training examples to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
