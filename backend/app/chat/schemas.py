"""Pydantic schemas for chat REST + WebSocket payloads."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


# -- REST -------------------------------------------------------------------- #
class CreateSessionIn(BaseModel):
    title: str | None = None


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    meta: dict[str, Any] | None = None
    created_at: datetime


# -- WebSocket: client -> server -------------------------------------------- #
class UserMessageIn(BaseModel):
    type: Literal["user_message"] = "user_message"
    content: str
    task_type: str = "reasoning"


# -- WebSocket: server -> client (discriminated by `type`) ------------------ #
class StartEvent(BaseModel):
    type: Literal["start"] = "start"


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    content: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    message_id: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    detail: str
