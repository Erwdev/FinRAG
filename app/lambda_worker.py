"""Handler Lambda finrag-worker (Architecture.md 3.2, 8.5, 14.12, 14.16).

Satu pesan SQS berisi {"job_id": "..."}. Batch size 1 (infra/terraform/modules/worker).
- Klaim atomik: UPDATE chat_job SET status='running' untuk queued atau status aktif yang stale.
  Pesan duplikat/ulangan tidak menjalankan job dua kali; retry bisa mengambil alih job yang stale.
- Pembatalan: job:{id}:cancel dicek sebelum klaim.
- Kesalahan infrastruktur (DB, Redis) dilempar ulang agar SQS mencoba lagi lalu masuk DLQ.
  Kesalahan pipeline sudah ditandai failed di dalam run_chat_job dan tidak diulang.
- Sentry dan Langfuse di-flush sebelum handler kembali.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from sqlalchemy import and_, or_, update

from app.agent.pipeline import run_chat_job
from app.cache import get_redis, utc_now_iso
from app.db.models import ChatJob
from app.db.session import get_sessionmaker
from app.redis_keys import job, job_cancel, job_events
from app.settings import get_settings

log = logging.getLogger("finrag.worker")


async def _claim(session, job_id: uuid.UUID) -> bool:
    """Klaim atomik queued/stale-active -> running. True bila baris ini berhasil diambil."""
    import datetime as dt

    now = dt.datetime.now(dt.timezone.utc)
    stale_before = now - dt.timedelta(seconds=150)
    active_statuses = ("running", "planning", "retrieving", "ranking", "generating", "validating")
    stmt = (
        update(ChatJob)
        .where(
            ChatJob.id == job_id,
            or_(
                ChatJob.status == "queued",
                and_(ChatJob.status.in_(active_statuses), ChatJob.updated_at < stale_before),
            ),
        )
        .values(status="running", updated_at=now)
        .returning(ChatJob.id)
    )
    claimed = (await session.execute(stmt)).scalar_one_or_none()
    await session.commit()
    return claimed is not None


async def _cancel_before_claim(session, rd, job_id: uuid.UUID) -> None:
    """Pembatalan sebelum job sempat diklaim: tandai cancelled dan catat event."""
    import datetime as dt

    now = dt.datetime.now(dt.timezone.utc)
    await session.execute(
        update(ChatJob)
        .where(ChatJob.id == job_id, ChatJob.status == "queued")
        .values(status="cancelled", finished_at=now, updated_at=now)
    )
    await session.commit()
    seq = int(rd.llen(job_events(str(job_id))) or 0) + 1
    rd.rpush(
        job_events(str(job_id)),
        json.dumps({"seq": seq, "ts": utc_now_iso(), "type": "job.cancelled", "stage": "cancelled",
                    "message": "dibatalkan sebelum diproses", "data": {}}),
    )
    rd.hset(job(str(job_id)), values={"status": "cancelled", "progress": "100", "updated_at": utc_now_iso()})


async def process_job(job_id: str) -> str:
    """Return ringkasan: claimed, skipped, atau cancelled."""
    jid = uuid.UUID(job_id)
    rd = get_redis()
    maker = get_sessionmaker()
    async with maker() as session:
        if rd.get(job_cancel(job_id)):
            await _cancel_before_claim(session, rd, jid)
            return "cancelled"
        if not await _claim(session, jid):
            log.info("job %s sudah diklaim atau selesai, dilewati", job_id)
            return "skipped"
        await run_chat_job(session, rd, jid)
    return "claimed"


def _flush_observability() -> None:
    """Sentry dan Langfuse harus terkirim sebelum Lambda membeku (14.16). Modul opsional."""
    s = get_settings()
    try:
        import sentry_sdk

        sentry_sdk.flush(timeout=2)
    except ImportError:
        pass
    if s.langfuse_public_key and s.langfuse_secret_key:
        try:
            from langfuse import get_client

            get_client().flush()
        except ImportError:
            pass


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    results: list[str] = []
    try:
        for record in event.get("Records", []):
            body = json.loads(record["body"])
            job_id = str(body["job_id"])
            # Kesalahan di sini dilempar ulang: SQS mencoba lagi, lalu DLQ setelah batas percobaan.
            results.append(asyncio.run(process_job(job_id)))
    finally:
        _flush_observability()
    return {"results": results}
