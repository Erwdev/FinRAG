-- Skema dan tabel raw (Architecture.md 4.3). Idempoten: aman dijalankan ulang.
-- Dijalankan oleh scripts/init_motherduck.py dan oleh flow ingest sebelum memuat.
-- Kolom daftar disimpan sebagai JSON (tickers_json) karena max_table_nesting=0 (bagian 4.2 aturan 1).

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.raw_ohlcv (
    ticker        VARCHAR NOT NULL,
    ts            TIMESTAMP NOT NULL,
    open          DOUBLE,
    high          DOUBLE,
    low           DOUBLE,
    close         DOUBLE,
    volume        DOUBLE,
    source        VARCHAR NOT NULL,
    _dlt_load_id  VARCHAR,
    _ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    _source_file  VARCHAR
);

CREATE TABLE IF NOT EXISTS raw.raw_articles (
    article_id    VARCHAR NOT NULL,
    url           VARCHAR,
    title         VARCHAR,
    summary       VARCHAR,
    published_at  TIMESTAMP,
    source        VARCHAR,
    tickers_json  VARCHAR,
    _dlt_load_id  VARCHAR,
    _ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    _source_file  VARCHAR
);

CREATE TABLE IF NOT EXISTS raw.raw_tweets (
    tweet_id      VARCHAR NOT NULL,
    text          VARCHAR,
    author        VARCHAR,
    created_at    TIMESTAMP,
    ticker_query  VARCHAR,
    url           VARCHAR,
    _dlt_load_id  VARCHAR,
    _ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    _source_file  VARCHAR
);
