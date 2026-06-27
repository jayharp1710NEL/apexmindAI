"""Safety API: emergency stop + human approval of Level >=3 tool actions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/safety", tags=["safety"])


class EngageIn(BaseModel):
    reason: str = "manual"


class ResolveIn(BaseModel):
    approved: bool


@router.get("/estop")
async def estop_status(request: Request) -> dict:
    engaged = await request.app.state.estop.is_engaged()
    return {"engaged": engaged}


@router.post("/estop/engage")
async def estop_engage(body: EngageIn, request: Request) -> dict:
    await request.app.state.estop.engage(body.reason)
    return {"engaged": True, "reason": body.reason}


@router.post("/estop/clear")
async def estop_clear(request: Request) -> dict:
    await request.app.state.estop.clear()
    return {"engaged": False}


@router.get("/approvals")
async def list_approvals(request: Request) -> list[dict]:
    return [
        {
            "id": r.id,
            "tool_name": r.tool_name,
            "level": r.level,
            "session_id": r.session_id,
            "detail": r.detail,
            "created_at": r.created_at.isoformat(),
        }
        for r in request.app.state.approvals.pending()
    ]


@router.post("/approvals/{approval_id}/resolve")
async def resolve_approval(
    approval_id: str, body: ResolveIn, request: Request
) -> dict:
    ok = request.app.state.approvals.resolve(approval_id, body.approved)
    if not ok:
        raise HTTPException(404, "approval not found or already resolved")
    return {"id": approval_id, "approved": body.approved}
