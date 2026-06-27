"""Shared application dependencies / singletons.

Kept deliberately small. Routes read the LLM interface and DB session factory from
`app.state` so tests can inject fakes without monkeypatching imports.
"""

from __future__ import annotations

from fastapi import Request, WebSocket

from app.router.interface import LLMInterface


def get_llm(request: Request) -> LLMInterface:
    return request.app.state.llm


def get_llm_ws(websocket: WebSocket) -> LLMInterface:
    return websocket.app.state.llm


def get_session_factory(request: Request):
    return request.app.state.session_factory
