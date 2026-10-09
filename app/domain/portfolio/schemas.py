from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

MAX_TICKERS = 10


class HoldingIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    quantity: Decimal = Field(gt=0)
    avg_cost: Decimal | None = Field(default=None, ge=0)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        return v.strip().upper()


class HoldingOut(BaseModel):
    ticker: str
    quantity: Decimal
    avg_cost: Decimal | None


class PortfolioIn(BaseModel):
    holdings: list[HoldingIn] = Field(max_length=MAX_TICKERS)


class PortfolioOut(BaseModel):
    holdings: list[HoldingOut]


class MeOut(BaseModel):
    id: str
    email: str
    role: str
