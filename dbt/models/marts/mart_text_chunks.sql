{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='chunk_id'
) }}

-- Chunk teks per ticker (bagian 4.3). Panjang 800 karakter, step 700 (overlap 100), maksimum 4 chunk per sumber.
-- Teks yang menyebut beberapa ticker menghasilkan satu baris per ticker.
with src as (
    select
        'news' as source_type,
        article_id as source_id,
        url,
        published_at,
        title || '. ' || summary as text,
        tickers
    from {{ ref('stg_articles') }}

    union all

    select
        'tweet' as source_type,
        tweet_id as source_id,
        url,
        created_at as published_at,
        text,
        tickers
    from {{ ref('stg_tweets') }}
),

chunked as (
    select
        s.source_type,
        s.source_id,
        s.url,
        s.published_at,
        t.ticker,
        s.text,
        n.i
    from src s,
        unnest(s.tickers) as t(ticker)
    cross join generate_series(0, 3) as n(i)
    where n.i * 700 < length(s.text)
)

select
    md5(source_id || '|' || cast(i as varchar) || '|' || ticker) as chunk_id,
    ticker,
    source_type,
    source_id,
    url,
    published_at,
    substr(text, i * 700 + 1, 800) as text,
    md5(substr(text, i * 700 + 1, 800)) as chunk_hash,
    now() as ingested_at
from chunked

{% if is_incremental() %}
where published_at >= (
    select coalesce(max(published_at), timestamp '1970-01-01') - interval 2 day
    from {{ this }}
)
{% endif %}
