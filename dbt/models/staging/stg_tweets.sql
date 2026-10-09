-- Dedupe per tweet_id, buang retweet murni, normalisasi spasi dan URL (bagian 4.3).
with ranked as (
    select
        tweet_id,
        trim(url) as url,
        trim(regexp_replace(coalesce(text, ''), '\s+', ' ', 'g')) as text,
        author,
        cast(created_at as timestamp) as created_at,
        upper(ticker_query) as ticker_query,
        _ingested_at,
        row_number() over (partition by tweet_id order by _ingested_at desc) as rn
    from {{ source('raw', 'raw_tweets') }}
)

select
    tweet_id,
    url,
    text,
    author,
    created_at,
    list_value(ticker_query) as tickers
from ranked
where rn = 1
  and text <> ''
  and not regexp_matches(text, '^RT @')
