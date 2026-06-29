"""Feedback API: capture ratings/corrections as training examples."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.feedback import store

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    prompt: str
    answer: str
    rating: Literal["up", "down"]
    correction: str | None = None  # the better answer, when rating is "down"
    model: str | None = None
    session_id: str | None = None


@router.post("")
async def submit_feedback(body: FeedbackIn) -> dict:
    # The "target" is what we'd want the model to say next time: the original
    # answer if it was good, or the user's correction if it was bad.
    target = body.answer if body.rating == "up" else (body.correction or body.answer)
    return store.append_example({
        "messages": [
            {"role": "user", "content": body.prompt},
            {"role": "assistant", "content": target},
        ],
        "rating": body.rating,
        "model": body.model,
        "session_id": body.session_id,
        "original_answer": body.answer if body.rating == "down" else None,
    })


@router.get("/count")
async def feedback_count() -> dict:
    return {"examples": store.count_examples()}
