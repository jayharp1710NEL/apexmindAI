"""Shared test config. Ensures the backend root is importable as `app`."""

from __future__ import annotations

import sys
from pathlib import Path

# backend/ root on sys.path so `import app...` works when running pytest anywhere.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
