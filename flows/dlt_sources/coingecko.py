"""Fallback harga CoinGecko (Architecture.md 4.5 dan 12). Dipakai bila Binance menolak IP (451/403) atau gagal.

Hanya menyediakan close harian. open, high, low diisi sama dengan close (bagian 4.3).
Retry memakai app/infra/retry.py (error sementara saja).
"""

from __future__ import annotations

import os

import httpx

from app.infra.retry import transient_retry
from flows.dlt_sources.common import utc_naive_from_ms

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


@transient_retry(attempts=2)
def coingecko_chart(coin_id: str, days: int) -> dict:
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


def rows_coingecko(symbol: str, coin_id: str, days: int) -> list[dict]:
    payload = coingecko_chart(coin_id, max(days, 1))
    rows = []
    for ts_ms, price in payload.get("prices", []):
        p = float(price)
        rows.append(
            {
                "ticker": symbol,
                "ts": utc_naive_from_ms(int(ts_ms)).replace(hour=0, minute=0, second=0, microsecond=0),
                "open": p,
                "high": p,
                "low": p,
                "close": p,
                "volume": None,
                "source": "coingecko",
            }
        )
    return rows
