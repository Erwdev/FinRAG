"""Prompt templates (Architecture.md 6.2 and 6.3).

The text lives in config/prompts.yaml (see app/agent/prompt_store.py). This module only wraps it
in ChatPromptTemplate. Variable values (question, evidence) are never parsed as template text.
"""

from langchain_core.prompts import ChatPromptTemplate  # noqa: E402

from app.agent.prompt_store import get_prompts

_P = get_prompts()

PLANNER_PROMPT = ChatPromptTemplate.from_messages([("system", _P["planner_system"]), ("human", _P["planner_user"])])
FINAL_PROMPT = ChatPromptTemplate.from_messages([("system", _P["final_system"]), ("human", _P["final_user"])])
REPAIR = _P["repair"]


def evidence_item(chunk_id: str, ticker: str, source_type: str, published_iso: str, age_hours: float, text: str) -> str:
    """Satu evidence sesuai bagian 6.2."""
    return (
        f'<item id="{chunk_id}" ticker="{ticker}" source="{source_type}" '
        f'published="{published_iso}" age_hours="{age_hours:.0f}">{text}</item>'
    )
