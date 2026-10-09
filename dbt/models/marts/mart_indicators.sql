-- Indikator dari bar tertutup saja (bagian 4.3). EMA12 dan EMA26 dihitung di Python (app/indicators.py).
-- Nilai di bawah jumlah bar minimum dibiarkan NULL.
with base as (
    select ticker, trade_date, close
    from {{ ref('mart_ohlcv_1d') }}
    where is_closed
),

calc as (
    select
        ticker,
        trade_date,
        close,
        row_number() over (partition by ticker order by trade_date) as n,
        lag(close) over (partition by ticker order by trade_date) as prev_close,
        lag(close, 20) over (partition by ticker order by trade_date) as close_20_ago,
        avg(close) over w20 as sma20,
        avg(close) over w50 as sma50,
        avg(close) over w200 as sma200,
        stddev_pop(close) over w20 as sd20,
        max(close) over w252 as hi252
    from base
    window
        w20 as (partition by ticker order by trade_date rows between 19 preceding and current row),
        w50 as (partition by ticker order by trade_date rows between 49 preceding and current row),
        w200 as (partition by ticker order by trade_date rows between 199 preceding and current row),
        w252 as (partition by ticker order by trade_date rows between 251 preceding and current row)
),

with_returns as (
    select
        *,
        case when prev_close > 0 then close / prev_close - 1 end as ret
    from calc
),

with_ret_sd as (
    select
        *,
        stddev_pop(ret) over (partition by ticker order by trade_date rows between 19 preceding and current row) as ret_sd20
    from with_returns
)

select
    ticker,
    trade_date,
    close,
    case when n >= 20 then sma20 end as sma20,
    case when n >= 50 then sma50 end as sma50,
    case when n >= 200 then sma200 end as sma200,
    case when n >= 20 then sma20 + 2 * sd20 end as bb_upper,
    case when n >= 20 then sma20 - 2 * sd20 end as bb_lower,
    case when n >= 20 and sd20 > 0 then (close - (sma20 - 2 * sd20)) / (4 * sd20) end as band_pos,
    case when n >= 21 then ret_sd20 * 100 end as stdev20_pct,
    case when n >= 21 and close_20_ago > 0 then (close / close_20_ago - 1) * 100 end as roc20_pct,
    case when n >= 2 then (close / hi252 - 1) * 100 end as drawdown_252_pct
from with_ret_sd
