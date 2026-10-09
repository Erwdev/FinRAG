"""dlt resource raw_ohlcv: Binance klines 1d per ticker, fallback CoinGecko (Architecture.md 4.5).

Harga memakai schema_contract freeze (Architecture.md 4.2): perubahan kolom dari sumber gagal jelas saat tulis.
Waktu disimpan sebagai UTC naif agar konversi ke TIMESTAMP di MotherDuck deterministik.
FALLBACKS mencatat ticker yang memakai CoinGecko pada run terakhir (dibaca flow untuk event).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import dlt
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from app.domain.market.universe import load_universe
from flows.dlt_sources.coingecko import rows_coingecko
from flows.dlt_sources.common import utc_naive_from_ms

FALLBACKS: list[str] = []


@retry(stop=stop_after_attempt(2), wait=wait_fixed(1), reraise=True)
def _klines(base: str, pair: str, start_ms: int) -> list[list]:
    resp = httpx.get(
        f"{base.rstrip('/')}/api/v3/klines",
        params={"symbol": pair, "interval": "1d", "startTime": start_ms, "limit": 1000},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _rows_binance(symbol: str, data: list[list]) -> list[dict]:
    return [
        {
            "ticker": symbol,
            "ts": utc_naive_from_ms(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "source": "binance",
        }
        for k in data
    ]


@dlt.resource(
    name="raw_ohlcv",
    write_disposition="append",
    primary_key=("ticker", "ts", "source"),
    max_table_nesting=0,
    # Harga: kolom dan tipe dibekukan. Perubahan skema gagal saat tulis (Architecture.md 4.2).
    schema_contract={"columns": "freeze", "data_type": "freeze"},
)
def raw_ohlcv(
    backfill_days: int = 300,
    cursor=dlt.sources.incremental("ts", initial_value=None),
):
    base = os.environ.get("BINANCE_BASE_URL", "https://data-api.binance.vision")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    floor = now - timedelta(days=backfill_days)
    last = cursor.last_value
    start = max(floor, last - timedelta(days=2)) if last else floor
    start_ms = int(start.replace(tzinfo=timezone.utc).timestamp() * 1000)
    days = max((now - start).days + 1, 1)

    FALLBACKS.clear()
    for coin in load_universe():
        try:
            rows = _rows_binance(coin["symbol"], _klines(base, coin["binance"], start_ms))
        except Exception:  # noqa: BLE001 - Binance menolak IP (451/403) atau gagal: pakai CoinGecko
            FALLBACKS.append(coin["symbol"])
            rows = rows_coingecko(coin["symbol"], coin["coingecko"], days)
        if rows:
            yield rows
