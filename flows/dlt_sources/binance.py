"""dlt resource raw_ohlcv: Binance klines 1d per ticker, fallback CoinGecko market_chart (Architecture.md 4.5).

Waktu disimpan sebagai UTC naif agar konversi ke TIMESTAMP di MotherDuck deterministik.
FALLBACKS mencatat ticker yang memakai CoinGecko pada run terakhir (dibaca flow untuk event).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import dlt
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from app.universe import load_universe

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
FALLBACKS: list[str] = []


def _utc_naive(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)


@retry(stop=stop_after_attempt(2), wait=wait_fixed(1), reraise=True)
def _klines(base: str, pair: str, start_ms: int) -> list[list]:
    resp = httpx.get(
        f"{base.rstrip('/')}/api/v3/klines",
        params={"symbol": pair, "interval": "1d", "startTime": start_ms, "limit": 1000},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(2), wait=wait_fixed(1), reraise=True)
def _coingecko_chart(coin_id: str, days: int) -> dict:
    headers = {}
    key = os.environ.get("COINGECKO_API_KEY")
    if key:
        headers["x-cg-demo-api-key"] = key
    resp = httpx.get(
        f"{COINGECKO_BASE}/coins/{coin_id}/market_chart",
        params={"vs_currency": "usd", "days": days, "interval": "daily"},
        headers=headers,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _rows_binance(symbol: str, data: list[list]) -> list[dict]:
    return [
        {
            "ticker": symbol,
            "ts": _utc_naive(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "source": "binance",
        }
        for k in data
    ]


def _rows_coingecko(symbol: str, coin_id: str, days: int) -> list[dict]:
    # Fallback hanya menyediakan close harian. open, high, low diisi sama dengan close (bagian 4.3).
    payload = _coingecko_chart(coin_id, max(days, 1))
    rows = []
    for ts_ms, price in payload.get("prices", []):
        p = float(price)
        rows.append(
            {
                "ticker": symbol,
                "ts": _utc_naive(int(ts_ms)).replace(hour=0, minute=0, second=0, microsecond=0),
                "open": p,
                "high": p,
                "low": p,
                "close": p,
                "volume": None,
                "source": "coingecko",
            }
        )
    return rows


@dlt.resource(
    name="raw_ohlcv",
    write_disposition="append",
    primary_key=("ticker", "ts", "source"),
    max_table_nesting=0,
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
            rows = _rows_coingecko(coin["symbol"], coin["coingecko"], days)
        if rows:
            yield rows
