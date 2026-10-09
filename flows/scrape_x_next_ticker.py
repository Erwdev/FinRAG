"""Flow scrape_x_next_ticker (Architecture.md 4.5 PL-1, 6 run per hari).

Aturan wajib:
1. Token bucket x:bucket (SET NX EX 900): maksimum satu request ke X per 15 menit.
2. Antrean rotasi x:due (sorted set). Ticker dengan skor terendah dipilih.
3. Anggaran Firecrawl: fc:used:total dibandingkan dengan FIRECRAWL_CREDIT_BUDGET sebelum scrape.
4. Idempoten: dlt memakai state, dedupe tweet_id di staging.
Deployment memakai concurrency limit 1 dan retries 0 (prefect.yaml).
"""

import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prefect import flow, get_run_logger  # noqa: E402

from flows.config import load_secrets, md_rw_connection, redis_client, require_env  # noqa: E402
from flows.dlt_sources.x import raw_tweets  # noqa: E402
from flows.load import ensure_raw_tables, load_tables  # noqa: E402
from flows.sources.text_source import FirecrawlXSource  # noqa: E402

FLOW_NAME = "scrape_x_next_ticker"


@flow(name=FLOW_NAME, retries=0)
def scrape_x_next_ticker() -> dict:
    import dlt

    from app.infra.redis import mark_fresh, push_event
    from app.domain.market.redis_keys import FC_USED_TOTAL, X_BUCKET, X_DUE
    from app.domain.market.universe import load_universe

    log = get_run_logger()
    load_secrets()
    r = redis_client()

    # 1. Token bucket: satu request per 15 menit.
    if not r.set(X_BUCKET, uuid.uuid4().hex, nx=True, ex=900):
        push_event(r, "ingest.x.skipped_rate_limited", "token bucket X masih terpakai")
        return {"status": "skipped_rate_limited"}

    # 2. Anggaran kredit Firecrawl (kredit gratis sekali pakai).
    budget = int(require_env("FIRECRAWL_CREDIT_BUDGET"))
    used = int(r.get(FC_USED_TOTAL) or 0)
    if used >= budget:
        push_event(r, "ingest.x.skipped_budget", "anggaran kredit Firecrawl habis", used=used, budget=budget)
        return {"status": "skipped_budget"}

    # 3. Antrean rotasi: isi anggota yang belum ada, lalu ambil skor terendah.
    coins = {c["symbol"]: c for c in load_universe()}
    for symbol in coins:
        r.zadd(X_DUE, {symbol: 0}, nx=True)
    ticker = r.zrange(X_DUE, 0, 0)[0]
    coin = coins[ticker]

    # 4. Scrape. Bila gagal, rotasi tetap maju agar ticker ini tidak diulang terus.
    try:
        items, credits = FirecrawlXSource(require_env("FIRECRAWL_API_KEY")).search(coin["x_query"], ticker)
    except Exception as exc:  # noqa: BLE001
        r.incrby(FC_USED_TOTAL, 1)
        r.zadd(X_DUE, {ticker: time.time()})
        push_event(r, "ingest.x.failed", f"scrape X gagal untuk {ticker}", error=str(exc))
        log.warning("scrape X gagal untuk %s: %s", ticker, exc)
        return {"status": "failed", "ticker": ticker}

    r.incrby(FC_USED_TOTAL, credits)
    r.zadd(X_DUE, {ticker: time.time()})

    # 5. Tulis lewat dlt dan muat ke raw_tweets.
    rows = 0
    if items:
        pipeline = dlt.pipeline(
            pipeline_name="finrag_scrape_x",
            destination=dlt.destinations.filesystem(bucket_url=f"s3://{require_env('LANDING_BUCKET')}/dlt"),
            dataset_name="landing",
        )
        info = pipeline.run(raw_tweets(items), loader_file_format="parquet")
        load_ids = [str(x) for x in info.loads_ids]
        con = md_rw_connection()
        try:
            ensure_raw_tables(con)
            rows = load_tables(con, require_env("LANDING_BUCKET"), load_ids, ("raw_tweets",))["raw_tweets"]
        finally:
            con.close()

    mark_fresh(r, "x")
    push_event(r, "ingest.x.completed", f"X {ticker} dimuat", ticker=ticker, items=len(items), rows=rows)
    return {"status": "completed", "ticker": ticker, "items": len(items), "credits": credits, "rows": rows}
