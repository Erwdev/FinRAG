"""Planner (tahap 1 routing LLM, Architecture.md 6.2 dan 6.3)."""

from __future__ import annotations

from app.agent.llm import make_chat_model
from app.agent.prompts import PLANNER_SYSTEM, PLANNER_USER
from app.agent.schemas import Plan
from app.settings import get_settings


def run_planner(question: str, today: str, universe: list[str], tickers: list[str]) -> tuple[Plan, dict]:
    """Return (Plan, catatan panggilan untuk llm_calls)."""
    from langchain_core.messages import HumanMessage, SystemMessage

    s = get_settings()
    # Fallback juga harus mengembalikan Plan terstruktur, jadi with_structured_output dipasang di kedua cabang.
    primary = make_chat_model(s.planner_model).with_structured_output(Plan, include_raw=True)
    chain = primary
    if s.fallback_model:
        chain = primary.with_fallbacks(
            [make_chat_model(s.fallback_model).with_structured_output(Plan, include_raw=True)]
        )
    messages = [
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(
            content=PLANNER_USER.format(
                today=today,
                universe=", ".join(universe),
                tickers=", ".join(tickers) or "(kosong)",
                question=question,
            )
        ),
    ]
    raw = chain.invoke(messages)
    plan: Plan = raw["parsed"]
    ai = raw.get("raw")
    usage = getattr(ai, "usage_metadata", None) if ai is not None else None
    model = getattr(ai, "response_metadata", {}).get("model_name", s.planner_model) if ai is not None else s.planner_model
    return plan, {"stage": "planner", "model": model, "usage": usage}
