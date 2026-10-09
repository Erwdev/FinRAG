-- Satu baris per ticker dan trade_date (UTC). Bila Binance dan CoinGecko ada untuk hari yang sama, Binance menang.
-- is_closed: hanya bar hari sebelumnya dianggap tertutup (bagian 4.3).
select
    ticker,
    cast(ts as date) as trade_date,
    open,
    high,
    low,
    close,
    volume,
    source,
    cast(ts as date) < cast(timezone('UTC', now()) as date) as is_closed
from {{ ref('stg_ohlcv') }}
qualify row_number() over (
    partition by ticker, cast(ts as date)
    order by (source = 'binance') desc, ts desc
) = 1
