{{ config(materialized='view') }}

-- Panel feed: berita dan X dalam satu bentuk (bagian 4.3).
select
    'news' as source_type,
    article_id as source_id,
    tickers,
    title as headline,
    url,
    published_at
from {{ ref('stg_articles') }}

union all

select
    'tweet' as source_type,
    tweet_id as source_id,
    tickers,
    text as headline,
    url,
    created_at as published_at
from {{ ref('stg_tweets') }}
