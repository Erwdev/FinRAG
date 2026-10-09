from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.deps import CurrentUser, get_current_owner
from app.infra.redis import get_json, get_redis, set_json
from app.domain.market.indicators import chart_series
from app.infra.motherduck import MdCapExceeded, MdUnavailable, run_query
from app.domain.market.redis_keys import chart
from app.domain.market.universe import universe_symbols

router = APIRouter()

RANGE_DAYS = {"3m": 92, "6m": 183, "1y": 365}
CACHE_TTL = 300
WARMUP_BARS = 200  # bar tambahan untuk SMA200 dan EMA yang stabil


@router.get("/charts/{ticker}")
def get_chart(
    ticker: str,
    rng: Literal["3m", "6m", "1y"] = Query("3m", alias="range"),
    _: CurrentUser = Depends(get_current_owner),
) -> dict:
    symbol = ticker.upper()
    if symbol not in universe_symbols():
        raise HTTPException(404, "ticker not in universe")

    rd = get_redis()
    key = chart(symbol, rng)
    cached = get_json(rd, key)
    if cached is not None:
        return cached

    days = RANGE_DAYS[rng]
    try:
        _, rows = run_query(
            rd,
            "SELECT trade_date, close FROM finrag.mart.mart_ohlcv_1d "
            "WHERE ticker = ? AND is_closed ORDER BY trade_date DESC LIMIT ?",
            [symbol, days + WARMUP_BARS],
        )
    except MdCapExceeded:
        raise HTTPException(503, "compute quota reached; no new data served")
    except MdUnavailable:
        raise HTTPException(503, "data warehouse unavailable")

    rows.reverse()
    dates = [str(row[0]) for row in rows]
    closes = [float(row[1]) for row in rows]
    series = chart_series(closes)[-days:]
    dates = dates[-days:]
    payload = {
        "ticker": symbol,
        "range": rng,
        "as_of": dates[-1] if dates else None,
        "points": [{"date": d, **p} for d, p in zip(dates, series)],
    }
    set_json(rd, key, payload, CACHE_TTL)
    return payload
