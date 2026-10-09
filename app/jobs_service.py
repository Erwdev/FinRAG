"""Logika pembuatan dan pembacaan job chat (Architecture.md 3.2, 5.4, 8, 9.2).

Status di Postgres (chat_job) adalah sumber kebenaran. Redis menyimpan progres dan event untuk polling.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from upstash_redis import Redis

from app.cache import push_event, utc_now_iso
from app.db.models import ChatJob, ChatSession
from app.guardrails.disclosures import get_disclosures
from app.job_queue import QueueUnavailable, enqueue_job
from app.redis_keys import (
    JOB_TTL_SECONDS,
    job,
    job_events,
)

TERMINAL_STATUSES = {"completed", "blocked", "insufficient", "handoff", "failed", "cancelled"}


def holdings_hash(holdings: list[tuple[str, str, str | None]]) -> str:
    """Hash stabil dari (ticker, quantity, avg_cost). Kunci cache daily brief."""
    canon = json.dumps(sorted(holdings), separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def create_session(session: AsyncSession, user_id: uuid.UUID, title: str | None) -> ChatSession:
    row = ChatSession(id=uuid.uuid4(), user_id=user_id, title=title, created_at=_now())
    session.add(row)
    await session.commit()
    return row


async def create_job(
    session: AsyncSession,
    rd: Redis,
    *,
    user_id: uuid.UUID,
    chat_session_id: uuid.UUID,
    kind: str,
    question: str | None,
    holdings_hash_value: str | None,
    language: str,
) -> ChatJob:
    """Tulis job ke Postgres, siapkan hash Redis, lalu kirim ke SQS. Gagal kirim = job failed."""
    now = _now()
    row = ChatJob(
        id=uuid.uuid4(),
        session_id=chat_session_id,
        user_id=user_id,
        kind=kind,
        status="queued",
        question=question,
        holdings_hash=holdings_hash_value,
        language=language,
        llm_calls=[],
        guardrail_log=[],
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()

    key = job(str(row.id))
    rd.hset(
        key,
        values={
            "status": "queued",
            "user_id": str(user_id),
            "kind": kind,
            "question": question or "",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "progress": "5",
            "result_json": "",
            "error_code": "",
        },
    )
    rd.expire(key, JOB_TTL_SECONDS)
    push_event(rd, "job.queued", "job masuk antrean", job_id=str(row.id))
    rd.rpush(job_events(str(row.id)), json.dumps({"seq": 1, "ts": utc_now_iso(), "type": "job.queued",
                                                  "stage": "queued", "message": "Job masuk antrean",
                                                  "data": {}}))
    rd.expire(job_events(str(row.id)), JOB_TTL_SECONDS)

    try:
        enqueue_job(str(row.id))
    except QueueUnavailable:
        row.status = "failed"
        row.error_code = "queue_unavailable"
        row.updated_at = _now()
        row.finished_at = row.updated_at
        await session.commit()
        rd.hset(key, values={"status": "failed", "error_code": "queue_unavailable"})
        raise
    return row


async def get_owned_job(session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> ChatJob | None:
    row = await session.get(ChatJob, job_id)
    if row is None or row.user_id != user_id:
        return None
    return row


async def find_cached_brief(
    session: AsyncSession, user_id: uuid.UUID, holdings_hash_value: str
) -> ChatJob | None:
    """Job daily_brief completed pada tanggal UTC yang sama dengan holdings_hash yang sama (bagian 5.4)."""
    start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    row = (
        await session.execute(
            select(ChatJob)
            .where(
                ChatJob.user_id == user_id,
                ChatJob.kind == "daily_brief",
                ChatJob.status == "completed",
                ChatJob.holdings_hash == holdings_hash_value,
                ChatJob.created_at >= start,
            )
            .order_by(ChatJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


def read_progress(rd: Redis, job_id: uuid.UUID, after_seq: int) -> dict:
    """Status dan progres dari Redis. Kosong bila hash sudah kedaluwarsa (fallback ke Postgres)."""
    h = rd.hgetall(job(str(job_id))) or {}
    events_raw = rd.lrange(job_events(str(job_id)), after_seq, -1) if after_seq >= 0 else []
    events = [json.loads(e) for e in events_raw]
    return {
        "status": h.get("status"),
        "progress": int(h["progress"]) if h.get("progress") else None,
        "events": events,
    }


def terminal_payload(row: ChatJob) -> dict:
    """Blok hasil untuk status terminal. Pengungkapan selalu ditulis server (bagian 6.6)."""
    return {
        "result": row.result,
        "disclosures": get_disclosures(row.language),
        "handoff_reason": row.handoff_reason,
    }
