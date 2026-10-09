-- Dedupe per (ticker, ts, source) dengan data terbaru, cast tipe, buang harga nol atau negatif (bagian 4.3).
with ranked as (
    select
        ticker,
        cast(ts as timestamp) as ts,
        cast(open as double) as open,
        cast(high as double) as high,
        cast(low as double) as low,
        cast(close as double) as close,
        cast(volume as double) as volume,
        source,
        _ingested_at,
        row_number() over (
            partition by ticker, ts, source
            order by _ingested_at desc
        ) as rn
    from {{ source('raw', 'raw_ohlcv') }}
    where open > 0 and high > 0 and low > 0 and close > 0
)

select ticker, ts, open, high, low, close, volume, source
from ranked
where rn = 1
