"""Flow build_and_embed (Architecture.md 4.5 dan 5.3): dbt build, lalu embedding chunk baru ke Pinecone.

Penjaga free tier wajib sebelum embedding (bagian 1.2 dan 14.11):
- EMBED_MONTHLY_TOKEN_CAP: counter embed:tokens:{yyyymm} dengan taksiran karakter dibagi 4.
- PINECONE_MAX_VECTORS: jumlah vektor di indeks ditambah chunk baru tidak boleh melebihi batas.
Chunk yang sudah ada di indeks (id = chunk_id) tidak diembed ulang.
"""

import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prefect import flow, get_run_logger  # noqa: E402

from app.infra.retry import transient_retry  # noqa: E402
from flows.config import dbt_dir, load_secrets, md_rw_connection, redis_client, require_env, single_run_lock  # noqa: E402

FLOW_NAME = "build_and_embed"
NAMESPACE = "default"
EMBED_BATCH = 48
UPSERT_BATCH = 100
FETCH_BATCH = 100
TEXT_METADATA_CHARS = 1500


def _values(item) -> list[float]:
    return item["values"] if isinstance(item, dict) else item.values


def _month() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m")


@transient_retry(attempts=3)
def _embed_passages(pc, model: str, texts: list[str]):
    # Retry hanya untuk error sementara (app/infra/retry.py). Embedding bersifat deterministik, jadi aman diulang.
    return pc.inference.embed(model=model, inputs=texts, parameters={"input_type": "passage", "truncate": "END"})


@transient_retry(attempts=3)
def _upsert(index, vectors: list[dict]) -> None:
    # Upsert dengan id tetap (chunk_id) bersifat idempoten: mengulang tidak menggandakan vektor.
    index.upsert(vectors=vectors, namespace=NAMESPACE)


def _pending_chunks(con) -> list[tuple]:
    return con.execute(
        "SELECT chunk_id, ticker, source_type, source_id, url, published_at, text, chunk_hash "
        "FROM mart.mart_text_chunks"
    ).fetchall()


@flow(name=FLOW_NAME, retries=0)
def build_and_embed() -> dict:
    from dbt.cli.main import dbtRunner
    from pinecone import Pinecone

    from app.infra.redis import mark_fresh, push_event
    from app.domain.market.redis_keys import embed_tokens

    log = get_run_logger()
    load_secrets()
    r = redis_client()

    with single_run_lock(r, FLOW_NAME) as acquired:
        if not acquired:
            return {"status": "skipped_locked"}

        # 1. dbt build. dbt-duckdb membaca token dari env MOTHERDUCK_TOKEN.
        os.environ["MOTHERDUCK_TOKEN"] = require_env("MOTHERDUCK_TOKEN_RW")
        res = dbtRunner().invoke(
            ["build", "--project-dir", str(dbt_dir()), "--profiles-dir", str(dbt_dir()), "--target", "prod"]
        )
        if not res.success:
            push_event(r, "build.failed", "dbt build gagal")
            raise RuntimeError("dbt build gagal")
        mark_fresh(r, "build")
        push_event(r, "build.completed", "dbt build selesai")

        # 2. Chunk dari mart dan indeks yang sudah ada.
        pc = Pinecone(api_key=require_env("PINECONE_API_KEY"))
        index = pc.Index(require_env("PINECONE_INDEX"))
        con = md_rw_connection()
        try:
            chunks = _pending_chunks(con)
        finally:
            con.close()

        present: set[str] = set()
        ids = [c[0] for c in chunks]
        for i in range(0, len(ids), FETCH_BATCH):
            res_fetch = index.fetch(ids=ids[i : i + FETCH_BATCH], namespace=NAMESPACE)
            present.update(res_fetch.vectors.keys())
        new = [c for c in chunks if c[0] not in present]

        # 3. Penjaga kuota token embedding (bulanan).
        cap_tokens = int(require_env("EMBED_MONTHLY_TOKEN_CAP"))
        used = int(r.get(embed_tokens(_month())) or 0)
        selected, est_total = [], 0
        for c in new:
            est = max(len(c[6]) // 4, 1)
            if used + est_total + est > cap_tokens:
                push_event(r, "embed.skipped_quota", "kuota token embedding bulanan tercapai", pending=len(new))
                break
            selected.append(c)
            est_total += est

        # 4. Penjaga jumlah vektor di indeks.
        max_vectors = int(require_env("PINECONE_MAX_VECTORS"))
        total_vectors = int(index.describe_index_stats().total_vector_count)
        room = max(max_vectors - total_vectors, 0)
        if len(selected) > room:
            push_event(r, "quota.alert", "PINECONE_MAX_VECTORS hampir tercapai", total=total_vectors, room=room)
            selected = selected[:room]
            est_total = sum(max(len(c[6]) // 4, 1) for c in selected)

        # 5. Embedding passage lalu upsert.
        model = require_env("EMBEDDING_MODEL")
        upserted = 0
        for i in range(0, len(selected), UPSERT_BATCH):
            batch = selected[i : i + UPSERT_BATCH]
            vectors = []
            for j in range(0, len(batch), EMBED_BATCH):
                sub = batch[j : j + EMBED_BATCH]
                emb = _embed_passages(pc, model, [c[6] for c in sub])
                for c, e in zip(sub, emb):
                    vectors.append((c, _values(e)))
            _upsert(
                index,
                [{"id": c[0], "values": vec, "metadata": _metadata(c)} for c, vec in vectors],
            )
            # Catat token per batch setelah upsert berhasil, agar kegagalan di tengah tidak melewati kuota.
            batch_tokens = sum(max(len(c[6]) // 4, 1) for c in batch)
            r.incrby(embed_tokens(_month()), batch_tokens)
            upserted += len(vectors)

        push_event(r, "embed.completed", "chunk baru di-embed", upserted=upserted, pending=len(new))
        log.info("build_and_embed: %d baru, %d di-upsert", len(new), upserted)
        return {"status": "completed", "pending": len(new), "upserted": upserted}


def _metadata(c: tuple) -> dict:
    _, ticker, source_type, source_id, url, published_at, text, chunk_hash = c
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=dt.timezone.utc)
    return {
        "ticker": ticker,
        "source_type": source_type,
        "source_id": source_id,
        "url": url or "",
        "published_at_ts": int(published_at.timestamp()),
        "chunk_hash": chunk_hash,
        "text": text[:TEXT_METADATA_CHARS],
    }
