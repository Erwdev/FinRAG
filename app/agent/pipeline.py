"""Pipeline job chat (Architecture.md 3.2, 5.1 sampai 5.4, 6.4, 8.2, 8.4).

run_chat_job menjalankan satu job yang sudah diklaim worker (status running di Postgres).
Setiap transisi status menulis chat_job, event Redis (8.2), dan guardrail_log.
Kegagalan yang terduga ditandai failed dan tidak dilempar ulang, supaya pesan SQS tidak diulang tanpa henti.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import evidence_blocks, indicators_yaml, portfolio_yaml, render_evidence
from app.agent.llm import LlmNotConfigured, make_chat_model
from app.agent.planner import run_planner
from app.agent.prompts import FINAL_SYSTEM, FINAL_USER, REPAIR
from app.agent.retrieval import search_text
from app.agent.schemas import Plan, Recommendation
from app.agent.tools import get_indicators, get_last_prices, get_portfolio
from app.cache import utc_now_iso
from app.db.models import ChatJob, Holding
from app.guardrails.disclosures import get_disclosures
from app.guardrails.rails import input_rail, output_rail, scope_rail
from app.md import MdCapExceeded, MdUnavailable
from app.redis_keys import cost_llm, job, job_cancel, job_events
from app.settings import get_settings
from app.universe import universe_symbols

DAILY_BRIEF_WINDOW_DAYS = 2
MICRO_USD = 1_000_000

# Progres per event (8.2). Status setelahnya diisi eksplisit di setiap pemanggilan _emit.
PROGRESS = {
    "job.started": 10, "guard.input.passed": 15, "plan.started": 20, "plan.completed": 30,
    "retrieve.indicators.completed": 40, "retrieve.portfolio.completed": 45,
    "retrieve.vector.started": 50, "retrieve.vector.completed": 60, "guard.retrieval.passed": 65,
    "rank.completed": 70, "context.built": 75, "llm.final.started": 80, "guard.output.repaired": 85,
    "llm.final.completed": 90, "guard.output.passed": 93, "guard.scope.passed": 96,
}


class _Run:
    """Keadaan satu job selama pipeline berjalan. Kunci Redis dan seq event dihitung di sini."""

    def __init__(self, session: AsyncSession, rd, row: ChatJob):
        self.session = session
        self.rd = rd
        self.row = row
        self.job_id = str(row.id)
        self.started = time.monotonic()
        self.seq = int(rd.llen(job_events(self.job_id)) or 0)

    async def emit(self, event: str, status: str | None, message: str, progress: int | None = None, **data):
        """Tulis event ke Redis, perbarui hash job, dan simpan status ke Postgres bila berubah."""
        self.seq += 1
        ts = utc_now_iso()
        stage = status or self.row.status
        progress = PROGRESS.get(event, progress if progress is not None else 100)
        self.rd.rpush(
            job_events(self.job_id),
            json.dumps({"seq": self.seq, "ts": ts, "type": event, "stage": stage,
                        "message": message, "data": data}, default=str),
        )
        fields = {"progress": str(progress), "updated_at": ts}
        if status:
            fields["status"] = status
        self.rd.hset(job(self.job_id), values=fields)
        self.row.guardrail_log = [*(self.row.guardrail_log or []), {"event": event, "ts": ts}]
        if status and status != self.row.status:
            self.row.status = status
        self.row.updated_at = dt.datetime.now(dt.timezone.utc)
        await self.session.commit()

    async def finish(self, status: str, event: str, message: str, **data):
        """Status terminal: set finished_at, latency, dan kirim event penutup."""
        self.row.finished_at = dt.datetime.now(dt.timezone.utc)
        self.row.latency_ms = int((time.monotonic() - self.started) * 1000)
        await self.emit(event, status, message, progress=100, **data)

    def cancelled(self) -> bool:
        return bool(self.rd.get(job_cancel(self.job_id)))


def _today_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def _budget_exceeded(rd) -> bool:
    spent = int(rd.get(cost_llm(dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d"))) or 0)
    return spent >= get_settings().daily_llm_budget_usd * MICRO_USD


async def _holdings(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = (await session.execute(select(Holding).where(Holding.user_id == user_id))).scalars().all()
    return [{"ticker": h.ticker, "quantity": h.quantity, "avg_cost": h.avg_cost} for h in rows]


def _fixed_brief_plan(tickers: list[str], language: str) -> Plan:
    """Plan tetap daily_brief (5.4): tanpa panggilan planner."""
    return Plan(
        intent="daily_brief", wants_assessment=True, language=language, tickers=tickers,
        need_indicators=True, need_text=True, text_window_days=DAILY_BRIEF_WINDOW_DAYS,
        text_source_types=["news", "tweet"],
    )


async def run_chat_job(session: AsyncSession, rd, job_id: uuid.UUID) -> None:
    """Jalankan pipeline untuk satu job. Dipanggil oleh worker setelah klaim atomik."""
    row = await session.get(ChatJob, job_id)
    if row is None or row.status != "running":
        return
    run = _Run(session, rd, row)
    try:
        await _pipeline(run)
    except MdCapExceeded:
        await run.finish("failed", "job.failed", "batas compute MotherDuck tercapai", error_code="md_cap")
    except MdUnavailable:
        await run.finish("failed", "job.failed", "MotherDuck tidak tersedia", error_code="md_unavailable")
    except LlmNotConfigured:
        await run.finish("failed", "job.failed", "LLM belum dikonfigurasi", error_code="llm_not_configured")
    except Exception:  # noqa: BLE001 - job ditandai gagal, bukan diulang tanpa henti
        await run.finish("failed", "job.failed", "kesalahan internal", error_code="internal")
    finally:
        row.latency_ms = row.latency_ms or int((time.monotonic() - run.started) * 1000)
        await session.commit()


async def _pipeline(run: _Run) -> None:
    row, rd = run.row, run.rd
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)

    await run.emit("job.started", "running", "job dimulai", progress=10)
    if run.cancelled():
        return await run.finish("cancelled", "job.cancelled", "dibatalkan")
    if _budget_exceeded(rd):
        return await run.finish("failed", "job.failed", "anggaran LLM harian habis", error_code="budget_exceeded")

    # Rail 1: input. Pertanyaan dibersihkan dulu (email dan kartu disamarkan).
    question, block = input_rail(row.question or "")
    if block:
        return await run.finish("blocked", "guard.input.blocked", f"ditolak: {block}", reason=block)
    await run.emit("guard.input.passed", "running", "input lolos pemeriksaan")

    universe = sorted(universe_symbols())
    holdings = await _holdings(run.session, row.user_id)
    holding_tickers = [h["ticker"] for h in holdings]

    # Rencana: daily_brief memakai Plan tetap, chat memakai planner LLM.
    if row.kind == "daily_brief":
        if not holding_tickers:
            return await run.finish("insufficient", "guard.retrieval.insufficient", "portofolio kosong")
        plan = _fixed_brief_plan(holding_tickers, row.language)
        await run.emit("plan.completed", "planning", "rencana tetap daily brief", source="fixed")
    else:
        await run.emit("plan.started", "planning", "menyusun rencana")
        plan, call = await _run_planner_safe(question, universe, holding_tickers)
        row.llm_calls = [*(row.llm_calls or []), {**call, "ts": utc_now_iso()}]
        row.language = plan.language
        if plan.intent == "refuse_execution":
            return await run.finish("blocked", "plan.refused", "permintaan eksekusi ditolak", intent=plan.intent)
        if plan.intent == "needs_human":
            row.handoff_reason = "needs_human"
            return await run.finish("handoff", "plan.handoff", "perlu tinjauan manusia",
                                    reason="needs_human")
        if plan.intent == "off_topic":
            return await run.finish("blocked", "plan.refused", "di luar topik", intent=plan.intent)
        await run.emit("plan.completed", "planning", "rencana disusun", tickers=plan.tickers)

    tickers = [t for t in plan.tickers if t in universe] or holding_tickers
    row.language = plan.language

    # Retrieval: indikator dan portofolio dari sumber terstruktur, lalu vektor teks.
    indicators: list[dict] = []
    if plan.need_indicators and tickers:
        indicators = get_indicators(rd, tickers)
        await run.emit("retrieve.indicators.completed", "retrieving", "indikator diambil", count=len(indicators))

    prices = get_last_prices(holding_tickers) if holding_tickers else {}
    portfolio = get_portfolio(holdings, prices)
    await run.emit("retrieve.portfolio.completed", "retrieving", "portofolio dihitung")

    evidence: list[dict] = []
    if plan.need_text and tickers:
        await run.emit("retrieve.vector.started", "retrieving", "pencarian teks")
        from pinecone import Pinecone

        pc = Pinecone(api_key=s.pinecone_api_key)
        result, chunks = search_text(
            pc, question, tickers, plan.text_window_days, plan.text_source_types, now
        )
        await run.emit("retrieve.vector.completed", "retrieving", "pencarian selesai", kept=len(result.kept))
        if not result.sufficient:
            return await run.finish(
                "insufficient", "guard.retrieval.insufficient", "bukti kurang",
                tickers=result.insufficient_tickers,
            )
        await run.emit("guard.retrieval.passed", "ranking", "bukti cukup")
        evidence = evidence_blocks(chunks, now)
    await run.emit("rank.completed", "ranking", "bukti diurutkan")

    # Konteks dan prompt. Teks evidence diperlakukan sebagai data tak tepercaya (6.2).
    ind_yaml = indicators_yaml(indicators)
    port_yaml = portfolio_yaml(portfolio["positions"])
    ev_text = render_evidence(evidence)
    assessment_requested = bool(plan.wants_assessment)
    user_msg = FINAL_USER.format(
        assessment_requested=str(assessment_requested).lower(),
        as_of=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        portfolio_yaml=port_yaml,
        indicators_yaml=ind_yaml,
        evidence_blocks=ev_text,
        question=question,
    )
    await run.emit("context.built", "generating", "konteks dibangun")

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(content=FINAL_SYSTEM), HumanMessage(content=user_msg)]
    await run.emit("llm.final.started", "generating", "jawaban final")
    rec = await _final_call(messages)
    row.llm_calls = [*(row.llm_calls or []), {"stage": "final", "model": s.final_model, "ts": utc_now_iso()}]
    await run.emit("llm.final.completed", "validating", "jawaban final diterima")

    # Rail 3: output. Satu kali perbaikan, lalu gagal bila masih salah.
    context_text = "\n".join([ind_yaml, port_yaml, ev_text])
    allowed_ids = {e["id"] for e in evidence}
    errors = output_rail(rec, allowed_ids, context_text, assessment_requested)
    if errors:
        await run.emit("guard.output.repaired", "generating", "perbaikan jawaban",
                       errors=errors)
        messages = [*messages, HumanMessage(content=REPAIR.format(errors="\n".join(errors)))]
        rec = await _final_call(messages)
        errors = output_rail(rec, allowed_ids, context_text, assessment_requested)
        if errors:
            return await run.finish("insufficient", "guard.output.failed", "jawaban tidak lolos validasi",
                                    errors=errors)
    await run.emit("guard.output.passed", "validating", "jawaban lolos validasi")

    # Rail 4: cakupan. Pelanggaran menghasilkan handoff, bukan perbaikan otomatis.
    reasons = scope_rail(rec, assessment_requested)
    if reasons:
        row.handoff_reason = "; ".join(reasons)
        return await run.finish("handoff", "guard.scope.handoff", "diteruskan ke pemilik", reasons=reasons)
    await run.emit("guard.scope.passed", "validating", "cakupan lolos")

    row.result = {
        "recommendation": rec.model_dump(mode="json"),
        "evidence": [{k: v for k, v in e.items() if k != "xml"} for e in evidence],
        "portfolio": portfolio,
        "indicators": indicators,
        "disclosures": get_disclosures(row.language),
    }
    await run.finish("completed", "job.completed", "job selesai")


async def _run_planner_safe(question: str, universe: list[str], tickers: list[str]):
    # Panggilan LLM sinkron dijalankan di thread agar event loop tidak terblokir.
    return await asyncio.to_thread(run_planner, question, _today_utc(), universe, tickers)


async def _final_call(messages) -> Recommendation:
    s = get_settings()
    primary = make_chat_model(s.final_model).with_structured_output(Recommendation)
    chain = primary
    if s.fallback_model:
        chain = primary.with_fallbacks(
            [make_chat_model(s.fallback_model).with_structured_output(Recommendation)]
        )
    return await asyncio.to_thread(chain.invoke, messages)
