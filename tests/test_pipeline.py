"""Tes pipeline chat tanpa jaringan: Redis dan Postgres dipalsukan di memori.

Mencakup jalur yang tidak memanggil LLM: rail input memblokir, dan planner menolak eksekusi.
Jalur final LLM dengan respx mock gateway belum ada (lihat todo.md).
"""

import json
import uuid

import pytest

from app.agent import pipeline
from app.agent.schemas import Plan
from app.db.models import ChatJob


class FakeRedis:
    def __init__(self):
        self.data: dict = {}
        self.lists: dict[str, list] = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, **_):
        self.data[key] = value

    def hset(self, key, values=None, **_):
        self.data.setdefault(key, {}).update(values or {})

    def expire(self, *_):
        return True

    def rpush(self, key, *values):
        self.lists.setdefault(key, []).extend(values)
        return len(self.lists[key])

    def llen(self, key):
        return len(self.lists.get(key, []))

    def ltrim(self, *_):
        return True

    def events(self, job_id):
        return [json.loads(e) for e in self.lists.get(f"job:{job_id}:events", [])]


class FakeResult:
    def scalars(self):
        return self

    def all(self):
        return []


class FakeSession:
    def __init__(self, row):
        self.row = row

    async def get(self, _model, _id):
        return self.row

    async def execute(self, _stmt):
        return FakeResult()

    async def commit(self):
        return None


def _job(question: str) -> ChatJob:
    return ChatJob(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        kind="chat",
        status="running",
        question=question,
        language="id",
        llm_calls=[],
        guardrail_log=[],
    )


@pytest.mark.asyncio
async def test_execution_request_is_blocked_before_any_llm_call(monkeypatch):
    def no_planner(*_args, **_kwargs):
        raise AssertionError("planner tidak boleh dipanggil untuk permintaan eksekusi")

    monkeypatch.setattr(pipeline, "run_planner", no_planner)
    row = _job("place a buy order for BTC now")
    rd = FakeRedis()

    await pipeline.run_chat_job(FakeSession(row), rd, row.id)

    assert row.status == "blocked"
    types = [e["type"] for e in rd.events(row.id)]
    assert "guard.input.blocked" in types
    assert rd.get(f"job:{row.id}")["status"] == "blocked"


@pytest.mark.asyncio
async def test_planner_refusal_ends_blocked(monkeypatch):
    plan = Plan(
        intent="refuse_execution", wants_assessment=False, language="en", tickers=[],
        need_indicators=False, need_text=False, text_window_days=7, text_source_types=[],
    )
    monkeypatch.setattr(pipeline, "run_planner", lambda *_a, **_k: (plan, {"stage": "planner"}))
    row = _job("what is the price of BTC?")
    rd = FakeRedis()

    await pipeline.run_chat_job(FakeSession(row), rd, row.id)

    assert row.status == "blocked"
    types = [e["type"] for e in rd.events(row.id)]
    assert "plan.refused" in types
    assert row.finished_at is not None


@pytest.mark.asyncio
async def test_non_running_job_is_ignored():
    row = _job("hello")
    row.status = "queued"
    rd = FakeRedis()

    await pipeline.run_chat_job(FakeSession(row), rd, row.id)

    assert row.status == "queued"
    assert rd.events(row.id) == []
