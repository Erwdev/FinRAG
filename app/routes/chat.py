"""POST /chat, POST /chat/daily-brief, GET /chat/sessions, GET /chat/sessions/{id}/messages (Architecture.md 9.2, 5.4)."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, get_current_owner
from app.cache import get_redis
from app.db.models import ChatJob, ChatSession, Holding
from app.db.session import get_session
from app.job_queue import QueueUnavailable
from app.jobs_service import (
    create_job,
    create_session,
    find_cached_brief,
    holdings_hash,
)
from app.guardrails.rails import input_rail
from app.redis_keys import IDEM_TTL_SECONDS, idem_brief, idem_chat, rl_brief, rl_chat

router = APIRouter()

CHAT_LIMIT_PER_HOUR = 20
BRIEF_FORCE_PER_DAY = 3
DEFAULT_LANGUAGE = "id"  # belum ada preferensi bahasa klien; bawaan id (bagian 5.4)


class ChatIn(BaseModel):
    session_id: uuid.UUID | None = None
    # Batas 500 karakter ditegakkan input rail di worker (kode penolakan too_long), bukan di sini.
    question: str = Field(min_length=1, max_length=2000)
    client_request_id: str = Field(min_length=8, max_length=64)


class BriefIn(BaseModel):
    client_request_id: str = Field(min_length=8, max_length=64)
    force: bool = False


def _job_response(row: ChatJob, cached: bool = False) -> dict:
    return {
        "job_id": str(row.id),
        "session_id": str(row.session_id),
        "status": row.status,
        "cached": cached,
    }


def _quota_error(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, msg)


async def _get_idempotent_job(session: AsyncSession, rd, uid: uuid.UUID, key: str) -> ChatJob | None:
    existing = rd.get(key)
    if not existing:
        return None
    if str(existing).startswith("pending:"):
        raise HTTPException(409, "permintaan sedang diproses")
    row = await session.get(ChatJob, uuid.UUID(existing))
    if row is not None and row.user_id == uid:
        return row
    return None


@router.post("/chat", status_code=202)
async def post_chat(
    body: ChatIn,
    user: CurrentUser = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
):
    rd = get_redis()
    uid = uuid.UUID(user.id)
    question, block = input_rail(body.question)
    if block:
        raise HTTPException(422, f"ditolak: {block}")

    # Idempotensi: klik ulang dengan client_request_id yang sama mengembalikan job yang sama.
    idem_key = idem_chat(user.id, body.client_request_id)
    hold_value = f"pending:{uuid.uuid4()}"
    existing_row = await _get_idempotent_job(session, rd, uid, idem_key)
    if existing_row is not None:
        return _job_response(existing_row)
    if not rd.set(idem_key, hold_value, nx=True, ex=IDEM_TTL_SECONDS):
        existing_row = await _get_idempotent_job(session, rd, uid, idem_key)
        if existing_row is not None:
            return _job_response(existing_row)
        raise HTTPException(409, "permintaan sedang diproses")

    now = dt.datetime.now(dt.timezone.utc)
    hour_key = rl_chat(user.id, now.strftime("%Y%m%d%H"))
    count = rd.incr(hour_key)
    if count == 1:
        rd.expire(hour_key, 2 * 3600)
    if count > CHAT_LIMIT_PER_HOUR:
        rd.delete(idem_key)
        raise _quota_error("batas chat per jam tercapai")

    if body.session_id is not None:
        chat_session = await session.get(ChatSession, body.session_id)
        if chat_session is None or chat_session.user_id != uid:
            rd.delete(idem_key)
            raise HTTPException(404, "session not found")
    else:
        chat_session = await create_session(session, uid, title=question[:80])

    try:
        row = await create_job(
            session,
            rd,
            user_id=uid,
            chat_session_id=chat_session.id,
            kind="chat",
            question=question,
            holdings_hash_value=None,
            language=DEFAULT_LANGUAGE,
        )
    except QueueUnavailable:
        rd.delete(idem_key)
        raise HTTPException(503, "antrean job tidak tersedia")
    except Exception:
        rd.delete(idem_key)
        raise

    rd.set(idem_key, str(row.id), ex=IDEM_TTL_SECONDS)
    return _job_response(row)


@router.post("/chat/daily-brief")
async def post_daily_brief(
    body: BriefIn,
    response: Response,
    user: CurrentUser = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
):
    rd = get_redis()
    uid = uuid.UUID(user.id)
    idem_key = idem_brief(user.id, body.client_request_id)
    hold_value = f"pending:{uuid.uuid4()}"
    existing_row = await _get_idempotent_job(session, rd, uid, idem_key)
    if existing_row is not None:
        return _job_response(existing_row)
    if not rd.set(idem_key, hold_value, nx=True, ex=IDEM_TTL_SECONDS):
        existing_row = await _get_idempotent_job(session, rd, uid, idem_key)
        if existing_row is not None:
            return _job_response(existing_row)
        raise HTTPException(409, "permintaan sedang diproses")

    holdings = (
        await session.execute(select(Holding).where(Holding.user_id == uid).order_by(Holding.ticker))
    ).scalars().all()
    if not holdings:
        rd.delete(idem_key)
        raise HTTPException(422, "portofolio kosong")
    h = holdings_hash(
        [(x.ticker, str(x.quantity), None if x.avg_cost is None else str(x.avg_cost)) for x in holdings]
    )

    if not body.force:
        cached = await find_cached_brief(session, uid, h)
        if cached is not None:
            rd.set(idem_key, str(cached.id), ex=IDEM_TTL_SECONDS)
            response.status_code = 200
            return _job_response(cached, cached=True)
    else:
        day = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
        key = rl_brief(user.id, day)
        count = rd.incr(key)
        if count == 1:
            rd.expire(key, 2 * 24 * 3600)
        if count > BRIEF_FORCE_PER_DAY:
            rd.delete(idem_key)
            raise _quota_error("batas force daily brief per hari tercapai")

    chat_session = await create_session(session, uid, title="Rekomendasi Hari Ini")
    try:
        row = await create_job(
            session,
            rd,
            user_id=uid,
            chat_session_id=chat_session.id,
            kind="daily_brief",
            question=None,
            holdings_hash_value=h,
            language=DEFAULT_LANGUAGE,
        )
    except QueueUnavailable:
        rd.delete(idem_key)
        raise HTTPException(503, "antrean job tidak tersedia")
    except Exception:
        rd.delete(idem_key)
        raise

    rd.set(idem_key, str(row.id), ex=IDEM_TTL_SECONDS)
    response.status_code = 202
    return _job_response(row)


@router.get("/chat/sessions")
async def list_sessions(
    user: CurrentUser = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = (
        await session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == uuid.UUID(user.id))
            .order_by(ChatSession.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return {
        "sessions": [
            {"session_id": str(s.id), "title": s.title, "created_at": s.created_at.isoformat()}
            for s in rows
        ]
    }


@router.get("/chat/sessions/{session_id}/messages")
async def list_messages(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> dict:
    uid = uuid.UUID(user.id)
    chat_session = await session.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != uid:
        raise HTTPException(404, "session not found")
    rows = (
        await session.execute(
            select(ChatJob)
            .where(ChatJob.session_id == session_id)
            .order_by(ChatJob.created_at.asc())
        )
    ).scalars().all()
    return {
        "session_id": str(session_id),
        "messages": [
            {
                "job_id": str(r.id),
                "kind": r.kind,
                "status": r.status,
                "question": r.question,
                "result": r.result,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }
