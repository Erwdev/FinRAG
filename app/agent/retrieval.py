"""Retrieval vektor (Architecture.md 5.3): embedding query, Pinecone query, retrieval rail, re-rank."""

from __future__ import annotations

import datetime as dt

from app.domain.guardrails.rails import RailResult, rerank, retrieval_rail
from app.infra.retry import transient_retry
from app.settings import get_settings

TOP_K = 30
NAMESPACE = "default"
MAX_WINDOW_DAYS = 90


def _values(item) -> list[float]:
    return item["values"] if isinstance(item, dict) else item.values


def _field(obj, name):
    return obj[name] if isinstance(obj, dict) else getattr(obj, name)


@transient_retry(attempts=3)
def embed_query(pc, text: str) -> list[float]:
    s = get_settings()
    emb = pc.inference.embed(
        model=s.embedding_model,
        inputs=[text],
        parameters={"input_type": "query", "truncate": "END"},
    )
    return _values(emb[0])


@transient_retry(attempts=3)
def _query_index(index, **kwargs):
    # Query bersifat baca saja, aman diulang.
    return index.query(**kwargs)


def search_text(
    pc,
    question: str,
    tickers: list[str],
    window_days: int,
    source_types: list[str],
    now: dt.datetime,
) -> tuple[RailResult, list[dict]]:
    """Return (hasil rail, daftar chunk teratas setelah re-rank). Chunk kosong bila bukti kurang."""
    s = get_settings()
    window_days = max(1, min(window_days, MAX_WINDOW_DAYS))
    # Jendela waktu dibatasi juga oleh usia maksimum terpanjang per jenis sumber.
    cutoff = now - dt.timedelta(days=window_days)
    cutoff_ts = int(min(cutoff.timestamp(), now.timestamp()))

    vector = embed_query(pc, question)
    index = pc.Index(s.pinecone_index)
    res = _query_index(
        index,
        vector=vector,
        top_k=TOP_K,
        namespace=NAMESPACE,
        include_metadata=True,
        filter={
            "ticker": {"$in": tickers},
            "published_at_ts": {"$gte": cutoff_ts},
            "source_type": {"$in": source_types},
        },
    )
    matches = [
        {"id": _field(m, "id"), "score": float(_field(m, "score")), "metadata": dict(_field(m, "metadata"))}
        for m in _field(res, "matches")
    ]
    result = retrieval_rail(matches, tickers, now)
    if not result.sufficient:
        return result, []
    return result, rerank(result.kept, top_n=8)
