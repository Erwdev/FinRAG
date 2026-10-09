from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import CurrentUser, get_current_owner
from app.cache import get_json, get_redis, set_json
from app.md import MdCapExceeded, MdUnavailable, run_query
from app.redis_keys import SIGNALS_LATEST
from app.signals import describe
from app.universe import universe_symbols

router = APIRouter()
CACHE_TTL = 300

LATEST_SQL = """
SELECT ticker, trade_date, close, sma20, sma50, sma200, bb_upper, bb_lower,
       band_pos, stdev20_pct, roc20_pct, drawdown_252_pct
FROM finrag.mart.mart_indicators
QUALIFY row_number() OVER (PARTITION BY ticker ORDER BY trade_date DESC) = 1
"""


@router.get("/signals")
def get_signals(_: CurrentUser = Depends(get_current_owner)) -> dict:
    rd = get_redis()
    cached = get_json(rd, SIGNALS_LATEST)
    if cached is not None:
        return cached

    try:
        cols, rows = run_query(rd, LATEST_SQL)
    except MdCapExceeded:
        raise HTTPException(503, "compute quota reached; no new data served")
    except MdUnavailable:
        raise HTTPException(503, "data warehouse unavailable")

    allowed = universe_symbols()
    snapshots = [dict(zip(cols, row)) for row in rows]
    payload = {"signals": [describe(s) for s in snapshots if s["ticker"] in allowed]}
    set_json(rd, SIGNALS_LATEST, payload, CACHE_TTL)
    return payload
