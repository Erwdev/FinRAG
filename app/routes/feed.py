from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.deps import CurrentUser, get_current_owner
from app.cache import get_json, get_redis, set_json
from app.md import MdCapExceeded, MdUnavailable, run_query
from app.redis_keys import feed
from app.universe import universe_symbols

router = APIRouter()
CACHE_TTL = 120  # Architecture.md 8.1: feed:text, 2 menit


@router.get("/feed")
def get_feed(
    ticker: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    _: CurrentUser = Depends(get_current_owner),
) -> dict:
    symbol = ticker.upper() if ticker else None
    if symbol is not None and symbol not in universe_symbols():
        raise HTTPException(404, "ticker not in universe")

    rd = get_redis()
    key = feed(symbol or "all", limit)
    cached = get_json(rd, key)
    if cached is not None:
        return cached

    if symbol:
        sql = (
            "SELECT source_type, source_id, tickers, headline, url, published_at "
            "FROM finrag.mart.mart_feed WHERE list_contains(tickers, ?) "
            "ORDER BY published_at DESC LIMIT ?"
        )
        params: list = [symbol, limit]
    else:
        sql = (
            "SELECT source_type, source_id, tickers, headline, url, published_at "
            "FROM finrag.mart.mart_feed ORDER BY published_at DESC LIMIT ?"
        )
        params = [limit]

    try:
        cols, rows = run_query(rd, sql, params)
    except MdCapExceeded:
        raise HTTPException(503, "compute quota reached; no new data served")
    except MdUnavailable:
        raise HTTPException(503, "data warehouse unavailable")

    payload = {"items": [dict(zip(cols, row)) for row in rows]}
    set_json(rd, key, payload, CACHE_TTL)
    return payload
