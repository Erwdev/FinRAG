"""PriceSource: harga terakhir (Architecture.md 4.5 dan 5.2). Binance lalu CoinGecko sebagai fallback.

Dipakai API (/prices/live). Ingest historis ada di flows/dlt_sources/binance.py.
"""

from __future__ import annotations

import datetime as dt
import json

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from app.settings import get_settings
from app.universe import load_universe

COINGECKO_SIMPLE_PRICE = "https://api.coingecko.com/api/v3/simple/price"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@retry(stop=stop_after_attempt(2), wait=wait_fixed(0.5), reraise=True)
def _binance_latest(base: str, pairs: list[str]) -> dict[str, float]:
    resp = httpx.get(
        f"{base.rstrip('/')}/api/v3/ticker/price",
        params={"symbols": json.dumps(pairs, separators=(",", ":"))},
        timeout=10,
    )
    resp.raise_for_status()
    return {row["symbol"]: float(row["price"]) for row in resp.json()}


@retry(stop=stop_after_attempt(2), wait=wait_fixed(0.5), reraise=True)
def _coingecko_latest(ids: list[str], api_key: str | None) -> dict[str, float]:
    headers = {"x-cg-demo-api-key": api_key} if api_key else {}
    resp = httpx.get(
        COINGECKO_SIMPLE_PRICE,
        params={"ids": ",".join(ids), "vs_currencies": "usd"},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    return {k: float(v["usd"]) for k, v in resp.json().items()}


def latest_prices(symbols: list[str]) -> dict[str, dict]:
    """Return {symbol: {price, source, as_of}}. Simbol yang gagal di kedua sumber tidak disertakan."""
    s = get_settings()
    coins = {c["symbol"]: c for c in load_universe() if c["symbol"] in set(symbols)}
    now = _now_iso()
    out: dict[str, dict] = {}

    try:
        prices = _binance_latest(s.binance_base_url, [c["binance"] for c in coins.values()])
        for sym, c in coins.items():
            if c["binance"] in prices:
                out[sym] = {"price": prices[c["binance"]], "source": "binance", "as_of": now}
    except Exception:  # noqa: BLE001 - fallback untuk semua kegagalan Binance (termasuk 451 dan 403)
        pass

    missing = [sym for sym in coins if sym not in out]
    if missing:
        try:
            prices = _coingecko_latest([coins[sym]["coingecko"] for sym in missing], s.coingecko_api_key)
            for sym in missing:
                cg_id = coins[sym]["coingecko"]
                if cg_id in prices:
                    out[sym] = {"price": prices[cg_id], "source": "coingecko", "as_of": now}
        except Exception:  # noqa: BLE001
            pass

    return out
