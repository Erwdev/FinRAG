"""Flow ingest_daily (Architecture.md 4.5): harga Binance (fallback CoinGecko) dan berita RSS.

Alur: dlt menulis Parquet ke S3 landing -> muat ke raw MotherDuck (flows/load.py) -> set freshness.
Jadwal di prefect.yaml: 10 14 * * * UTC.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prefect import flow, get_run_logger, task  # noqa: E402

from flows.config import (  # noqa: E402
    load_secrets,
    md_rw_connection,
    redis_client,
    require_env,
    single_run_lock,
)
from flows.dlt_sources import binance, rss  # noqa: E402
from flows.load import ensure_raw_tables, load_tables  # noqa: E402

FLOW_NAME = "ingest_daily"


@task(retries=1, retry_delay_seconds=30)
def run_dlt(backfill_days: int) -> dict:
    import dlt

    bucket = require_env("LANDING_BUCKET")
    pipeline = dlt.pipeline(
        pipeline_name="finrag_ingest_daily",  # nama tetap agar state incremental terpulihkan
        destination=dlt.destinations.filesystem(bucket_url=f"s3://{bucket}/dlt"),
        dataset_name="landing",
    )
    price_info = pipeline.run(
        binance.raw_ohlcv(backfill_days=backfill_days), loader_file_format="parquet"
    )
    load_ids = [str(x) for x in price_info.loads_ids]
    fallbacks = list(binance.FALLBACKS)

    news_load_ids: list[str] = []
    news_error = None
    try:
        news_info = pipeline.run(
            rss.raw_articles(feed_url=require_env("NEWS_RSS_URL")), loader_file_format="parquet"
        )
        news_load_ids = [str(x) for x in news_info.loads_ids]
    except Exception as exc:  # noqa: BLE001 - berita gagal tidak menghentikan harga
        news_error = str(exc)

    return {
        "price_load_ids": load_ids,
        "news_load_ids": news_load_ids,
        "fallbacks": fallbacks,
        "news_error": news_error,
    }


@task
def load_into_md(result: dict) -> dict:
    bucket = require_env("LANDING_BUCKET")
    con = md_rw_connection()
    try:
        ensure_raw_tables(con)
        counts = load_tables(con, bucket, result["price_load_ids"], ("raw_ohlcv",))
        news = load_tables(con, bucket, result["news_load_ids"], ("raw_articles",))
        counts.update(news)
    finally:
        con.close()
    return counts


@flow(name=FLOW_NAME, retries=0)
def ingest_daily(backfill_days: int = 300) -> dict:
    log = get_run_logger()
    load_secrets()
    r = redis_client()

    from app.infra.redis import mark_fresh, push_event

    with single_run_lock(r, FLOW_NAME) as acquired:
        if not acquired:
            log.warning("ingest_daily sedang berjalan, run ini dilewati")
            return {"status": "skipped_locked"}

        result = run_dlt(backfill_days)
        counts = load_into_md(result)

        mark_fresh(r, "prices")
        push_event(r, "ingest.prices.completed", "harga harian dimuat", rows=counts.get("raw_ohlcv", 0))
        if result["fallbacks"]:
            push_event(
                r,
                "ingest.prices.fallback_coingecko",
                "Binance gagal untuk sebagian ticker, memakai CoinGecko",
                tickers=result["fallbacks"],
            )

        if result["news_error"]:
            push_event(r, "ingest.news.failed", "berita gagal, harga tetap dimuat", error=result["news_error"])
        else:
            mark_fresh(r, "news")
            push_event(r, "ingest.news.completed", "berita dimuat", rows=counts.get("raw_articles", 0))

        log.info("ingest_daily selesai: %s", counts)
        return {"status": "completed", "rows": counts, "fallbacks": result["fallbacks"]}
