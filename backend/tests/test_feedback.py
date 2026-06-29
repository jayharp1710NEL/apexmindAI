"""Feedback -> training dataset collection (no DB)."""

from __future__ import annotations

import json

from app.feedback import store


def test_append_and_count(tmp_path, monkeypatch):
    monkeypatch.setattr(store.settings, "training_data_dir", str(tmp_path))
    assert store.count_examples() == 0

    store.append_example({"messages": [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ], "rating": "up"})
    store.append_example({"messages": [
        {"role": "user", "content": "2+2"},
        {"role": "assistant", "content": "4"},
    ], "rating": "down"})

    assert store.count_examples() == 2
    lines = (tmp_path / "feedback.jsonl").read_text().strip().splitlines()
    first = json.loads(lines[0])
    assert first["messages"][1]["content"] == "hello"
    assert "ts" in first
