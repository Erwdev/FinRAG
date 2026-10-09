"""Skema Plan (planner) dan Recommendation (jawaban final), Architecture.md 6.2."""

from typing import Literal

from pydantic import BaseModel, Field


class Plan(BaseModel):
    intent: Literal[
        "daily_brief", "analyze_portfolio", "analyze_ticker", "news_summary",
        "compare", "refuse_execution", "needs_human", "off_topic",
    ]
    wants_assessment: bool
    language: Literal["id", "en"]
    tickers: list[str]
    need_indicators: bool
    need_text: bool
    text_window_days: int = Field(ge=1, le=90)
    text_source_types: list[Literal["news", "tweet"]]


class PositionView(BaseModel):
    ticker: str
    action: Literal["hold", "add", "reduce", "watch"] | None = None
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(max_length=600)
    risks: list[str] = Field(max_length=5)
    evidence_ids: list[str]


class Recommendation(BaseModel):
    as_of: str
    assessment_requested: bool
    positions: list[PositionView]
    portfolio_notes: str = Field(default="", max_length=800)
    insufficient_data: bool = False
