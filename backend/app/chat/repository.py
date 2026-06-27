"""Persistence helpers for chat: users, projects, sessions, messages.

Functions take an AsyncSession and never commit on their own (callers control the
transaction), except the get-or-create bootstrap which manages its own.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, Project, Session, User

DEFAULT_USER_EMAIL = "dev@apexmind.local"
DEFAULT_PROJECT_NAME = "Default"


async def get_or_create_default_context(
    session_factory,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Ensure a dev user + project exist; return (user_id, project_id).

    A convenience for the MVP so the UI can start chatting without an auth flow.
    """
    async with session_factory() as s, s.begin():
        user = await s.scalar(select(User).where(User.email == DEFAULT_USER_EMAIL))
        if user is None:
            user = User(email=DEFAULT_USER_EMAIL, name="Dev")
            s.add(user)
            await s.flush()
        project = await s.scalar(
            select(Project).where(
                Project.user_id == user.id, Project.name == DEFAULT_PROJECT_NAME
            )
        )
        if project is None:
            project = Project(user_id=user.id, name=DEFAULT_PROJECT_NAME)
            s.add(project)
            await s.flush()
        return user.id, project.id


async def create_session(
    s: AsyncSession,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None = None,
) -> Session:
    sess = Session(project_id=project_id, user_id=user_id, title=title)
    s.add(sess)
    await s.flush()
    return sess


async def list_sessions(s: AsyncSession, *, project_id: uuid.UUID) -> list[Session]:
    rows = await s.scalars(
        select(Session)
        .where(Session.project_id == project_id)
        .order_by(Session.created_at.desc())
    )
    return list(rows.all())


async def get_session(s: AsyncSession, session_id: uuid.UUID) -> Session | None:
    return await s.get(Session, session_id)


async def add_message(
    s: AsyncSession,
    *,
    session_id: uuid.UUID,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
    token_count: int | None = None,
) -> Message:
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        meta=meta,
        token_count=token_count,
    )
    s.add(msg)
    await s.flush()
    return msg


async def get_messages(s: AsyncSession, session_id: uuid.UUID) -> list[Message]:
    rows = await s.scalars(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    return list(rows.all())
