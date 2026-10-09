from fastapi import APIRouter, Depends

from app.auth.deps import CurrentUser, get_current_owner
from app.domain.market.universe import load_universe

router = APIRouter()


@router.get("/universe")
async def universe(_: CurrentUser = Depends(get_current_owner)) -> dict:
    coins = [
        {
            "symbol": c["symbol"],
            "name": c["name"],
            "binance_pair": c["binance"],
            "coingecko_id": c["coingecko"],
        }
        for c in load_universe()
    ]
    return {"coins": coins}
