from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import CurrentUser, get_current_owner
from app.cache import get_json, get_redis, set_json, utc_now_iso
from app.redis_keys import PRICE_LIVE
from app.sources.prices import latest_prices
from app.universe import universe_symbols

router = APIRouter()
CACHE_TTL = 15  # Architecture.md 8.1: price:live, 15 detik


@router.get("/prices/live")
def prices_live(_: CurrentUser = Depends(get_current_owner)) -> dict:
    rd = get_redis()
    cached = get_json(rd, PRICE_LIVE)
    if cached is not None:
        return cached

    prices = latest_prices(sorted(universe_symbols()))
    if not prices:
        raise HTTPException(503, "no price source available")
    payload = {"prices": prices, "as_of": utc_now_iso()}
    set_json(rd, PRICE_LIVE, payload, CACHE_TTL)
    return payload
