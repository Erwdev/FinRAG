-- Dedupe per article_id, bersihkan HTML dari title dan summary, pecah tickers_json menjadi VARCHAR[].
with ranked as (
    select
        article_id,
        url,
        regexp_replace(coalesce(title, ''), '<[^>]+>', ' ', 'g') as title,
        regexp_replace(coalesce(summary, ''), '<[^>]+>', ' ', 'g') as summary,
        cast(published_at as timestamp) as published_at,
        from_json(tickers_json, '["VARCHAR"]') as tickers,
        _ingested_at,
        row_number() over (partition by article_id order by _ingested_at desc) as rn
    from {{ source('raw', 'raw_articles') }}
)

select
    article_id,
    trim(url) as url,
    trim(regexp_replace(title, '\s+', ' ', 'g')) as title,
    trim(regexp_replace(summary, '\s+', ' ', 'g')) as summary,
    published_at,
    tickers
from ranked
where rn = 1
  and tickers is not null
  and len(tickers) > 0
