-- Uji kustom (bagian 4.3): close > 0 dan high >= low. Gagal bila ada baris yang melanggar.
select ticker, ts, source, open, high, low, close
from {{ ref('stg_ohlcv') }}
where close <= 0 or high < low
