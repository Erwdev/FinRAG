"""GET /jobs/{job_id}, POST /jobs/{job_id}/cancel (Architecture.md 8.1, 9.2)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, get_current_owner
from app.infra.postgres import get_session
from app.infra.redis import get_redis
from app.domain.chat.jobs_service import TERMINAL_STATUSES, get_owned_job, read_progress, terminal_payload
from app.domain.chat.redis_keys import CANCEL_TTL_SECONDS, job_cancel

router = APIRouter()


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    after_seq: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await get_owned_job(session, uuid.UUID(user.id), job_id)
    if row is None:
        raise HTTPException(404, "job not found")

    rd = get_redis()
    live = await run_in_threadpool(read_progress, rd, job_id, after_seq)
    status_now = row.status
    # Postgres lebih otoritatif untuk status terminal. Redis dipakai untuk progres dan event.
    if live["status"] and row.status not in TERMINAL_STATUSES:
        status_now = live["status"]

    body = {
        "job_id": str(job_id),
        "status": status_now,
        "progress": live["progress"],
        "events": live["events"],
    }
    if status_now in TERMINAL_STATUSES:
        body.update(terminal_payload(row))
    return body


@router.post("/jobs/{job_id}/cancel", status_code=202)
async def cancel_job(
    job_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await get_owned_job(session, uuid.UUID(user.id), job_id)
    if row is None:
        raise HTTPException(404, "job not found")
    if row.status in TERMINAL_STATUSES:
        return {"job_id": str(job_id), "status": row.status, "cancel_requested": False}
    # Worker memeriksa penanda ini di antara tahap (bagian 3.2). Tidak membatalkan panggilan LLM yang sedang berjalan.
    await run_in_threadpool(get_redis().set, job_cancel(str(job_id)), "1", ex=CANCEL_TTL_SECONDS)
    return {"job_id": str(job_id), "status": row.status, "cancel_requested": True}
