from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, get_current_owner
from app.db.models import Holding
from app.infra.postgres import get_session
from app.domain.portfolio.schemas import HoldingOut, PortfolioIn, PortfolioOut
from app.domain.market.universe import universe_symbols

router = APIRouter()


@router.get("/portfolio", response_model=PortfolioOut)
async def get_portfolio(
    user: CurrentUser = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> PortfolioOut:
    rows = (
        await session.execute(
            select(Holding).where(Holding.user_id == user.id).order_by(Holding.ticker)
        )
    ).scalars()
    return PortfolioOut(
        holdings=[HoldingOut(ticker=h.ticker, quantity=h.quantity, avg_cost=h.avg_cost) for h in rows]
    )


@router.put("/portfolio", response_model=PortfolioOut)
async def put_portfolio(
    body: PortfolioIn,
    user: CurrentUser = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> PortfolioOut:
    tickers = [h.ticker for h in body.holdings]
    if len(tickers) != len(set(tickers)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "duplicate ticker")

    allowed = universe_symbols()
    unknown = [t for t in tickers if t not in allowed]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"ticker not in universe: {unknown}")

    # Ganti seluruh holdings dalam satu transaksi (sesi dibuka otomatis oleh get_session).
    async with session.begin():
        await session.execute(delete(Holding).where(Holding.user_id == user.id))
        for h in body.holdings:
            session.add(
                Holding(user_id=user.id, ticker=h.ticker, quantity=h.quantity, avg_cost=h.avg_cost)
            )

    return await get_portfolio(user=user, session=session)
