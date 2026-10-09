"""Muat berkas Parquet dari S3 landing ke tabel raw MotherDuck (Architecture.md 4.2, aturan E2).

MotherDuck membaca S3 sendiri lewat secret persisten finrag_landing (dibuat scripts/init_motherduck.py).
Hanya berkas dari load_id yang diberikan yang dimuat. Duplikat dibuang di staging.
"""

from __future__ import annotations

import re
from pathlib import Path

import boto3

from flows.config import dbt_dir

LOAD_ID = re.compile(r"^[0-9.]+$")
DDL_PATH = dbt_dir() / "ddl" / "raw.sql"

INSERT_SQL = {
    "raw_ohlcv": """
        INSERT INTO raw.raw_ohlcv
            (ticker, ts, open, high, low, close, volume, source, _dlt_load_id, _ingested_at, _source_file)
        SELECT ticker, ts, open, high, low, close, volume, source, _dlt_load_id, now(), filename
        FROM read_parquet('{glob}', filename = true)
    """,
    "raw_articles": """
        INSERT INTO raw.raw_articles
            (article_id, url, title, summary, published_at, source, tickers_json, _dlt_load_id, _ingested_at, _source_file)
        SELECT article_id, url, title, summary, published_at, source, tickers_json, _dlt_load_id, now(), filename
        FROM read_parquet('{glob}', filename = true)
    """,
    "raw_tweets": """
        INSERT INTO raw.raw_tweets
            (tweet_id, text, author, created_at, ticker_query, url, _dlt_load_id, _ingested_at, _source_file)
        SELECT tweet_id, text, author, created_at, ticker_query, url, _dlt_load_id, now(), filename
        FROM read_parquet('{glob}', filename = true)
    """,
}


def ensure_raw_tables(con) -> None:
    """Jalankan DDL raw secara idempoten (CREATE ... IF NOT EXISTS)."""
    for stmt in DDL_PATH.read_text(encoding="utf-8").split(";"):
        body = "\n".join(line for line in stmt.splitlines() if not line.strip().startswith("--")).strip()
        if body:
            con.execute(body)


def load_tables(con, bucket: str, load_ids: list[str], tables: tuple[str, ...]) -> dict[str, int]:
    """Return {table: jumlah baris yang dimasukkan}. Tabel tanpa berkas untuk load_id tertentu dilewati."""
    s3 = boto3.client("s3")
    counts = {t: 0 for t in tables}
    for load_id in load_ids:
        if not LOAD_ID.match(load_id):
            raise ValueError(f"load_id tidak valid: {load_id!r}")
        for table in tables:
            prefix = f"dlt/landing/{table}/{load_id}."
            listing = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
            if listing.get("KeyCount", 0) == 0:
                continue
            glob = f"s3://{bucket}/{prefix}*.parquet"
            result = con.execute(INSERT_SQL[table].format(glob=glob)).fetchone()
            counts[table] += int(result[0]) if result else 0
    return counts
