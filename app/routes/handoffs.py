"""GET /handoffs, POST /handoffs/{job_id}/resolve (Architecture.md 9.2, 6.6). Hanya owner."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, get_current_owner
from app.clock import utc_now_iso
from app.db.models import ChatJob
from app.infra.postgres import get_session
from app.infra.redis import get_redis, push_event

router = APIRouter()


@router.get("/handoffs")
async def list_handoffs(
    user: CurrentUser = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = (
        await session.execute(
            select(ChatJob)
            .where(
                ChatJob.user_id == uuid.UUID(user.id),
                ChatJob.status == "handoff",
                ChatJob.handoff_resolved_at.is_(None),
            )
            .order_by(ChatJob.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return {
        "handoffs": [
            {
                "job_id": str(r.id),
                "session_id": str(r.session_id),
                "question": r.question,
                "handoff_reason": r.handoff_reason,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.post("/handoffs/{job_id}/resolve")
async def resolve_handoff(
    job_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await session.get(ChatJob, job_id)
    if row is None or row.user_id != uuid.UUID(user.id) or row.status != "handoff":
        raise HTTPException(404, "handoff not found")
    if row.handoff_resolved_at is not None:
        return {"job_id": str(job_id), "resolved": True, "already": True}

    row.handoff_resolved_at = dt.datetime.now(dt.timezone.utc)
    row.updated_at = row.handoff_resolved_at
    await session.commit()
    await run_in_threadpool(push_event, get_redis(), "handoff.resolved", "handoff ditutup pemilik", job_id=str(job_id))
    return {"job_id": str(job_id), "resolved": True, "resolved_at": utc_now_iso()}
