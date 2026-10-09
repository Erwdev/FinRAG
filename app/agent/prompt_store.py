"""Prompt store (Architecture.md 6.2).

get_prompts() returns the five prompt texts the agent uses. Sources:
1. config/prompts.yaml: always loaded and validated; the default and per-group fallback.
2. Langfuse Prompt Management: used when PROMPT_SOURCE=langfuse, label PROMPT_LABEL.
   Any failure for a group (SDK missing, network, empty or malformed prompt) falls back
   to the YAML text for that group only.

Langfuse prompt names (create these in the Langfuse UI):
- finrag-planner: chat, messages role=system (planner_system) and role=user (planner_user)
- finrag-final:   chat, messages role=system (final_system) and role=user (final_user)
- finrag-repair:  text
Langfuse uses {{var}} placeholders; they are converted to {var} for ChatPromptTemplate.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.settings import get_settings

log = logging.getLogger(__name__)

PROMPTS_PATH = Path(__file__).resolve().parents[2] / "config" / "prompts.yaml"
PROMPT_NAMES = ("planner_system", "planner_user", "final_system", "final_user", "repair")

# Langfuse prompt name -> keys it provides. Chat groups list keys in message order (system, user).
LANGFUSE_GROUPS: dict[str, tuple[str, ...]] = {
    "finrag-planner": ("planner_system", "planner_user"),
    "finrag-final": ("final_system", "final_user"),
    "finrag-repair": ("repair",),
}
_LANGFUSE_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@lru_cache(maxsize=1)
def default_prompts() -> dict[str, str]:
    """Read and validate config/prompts.yaml. Fails fast so a broken config never reaches a job."""
    data = yaml.safe_load(PROMPTS_PATH.read_text(encoding="utf-8")) or {}
    missing = [n for n in PROMPT_NAMES if not isinstance(data.get(n), str) or not data[n].strip()]
    if missing:
        raise RuntimeError(f"{PROMPTS_PATH.name} is missing or empty: {', '.join(missing)}")
    return {n: data[n] for n in PROMPT_NAMES}


def to_single_braces(text: str) -> str:
    """Convert Langfuse {{var}} placeholders to ChatPromptTemplate {var}."""
    return _LANGFUSE_PLACEHOLDER.sub(r"{\1}", text)


def _fetch_group(client: Any, name: str, keys: tuple[str, ...], label: str) -> dict[str, str]:
    """Fetch one Langfuse prompt and map its content to the local keys. Raises on any mismatch."""
    if keys == ("repair",):
        prompt = client.get_prompt(name, label=label)
        texts = {keys[0]: prompt.prompt}
    else:
        prompt = client.get_prompt(name, type="chat", label=label)
        by_role = {m["role"]: m["content"] for m in prompt.prompt}
        texts = {keys[0]: by_role["system"], keys[1]: by_role["user"]}

    result = {k: to_single_braces(str(v)) for k, v in texts.items()}
    empty = [k for k, v in result.items() if not v.strip()]
    if empty:
        raise ValueError(f"langfuse prompt {name} has empty content for: {', '.join(empty)}")
    return result


def _load_langfuse(defaults: dict[str, str]) -> dict[str, str]:
    """Return the defaults overridden by every Langfuse group that loads successfully."""
    from langfuse import get_client  # lazy: keeps cold start light when the source is file

    s = get_settings()
    client = get_client()
    merged = dict(defaults)
    for name, keys in LANGFUSE_GROUPS.items():
        try:
            merged.update(_fetch_group(client, name, keys, s.prompt_label))
        except Exception:
            log.warning("langfuse prompt %s unavailable, using yaml default", name, exc_info=True)
    return merged


def get_prompts() -> dict[str, str]:
    """Return the active prompt texts for the configured source."""
    defaults = default_prompts()
    if get_settings().prompt_source != "langfuse":
        return dict(defaults)
    try:
        return _load_langfuse(defaults)
    except Exception:
        log.warning("langfuse client unavailable, using yaml defaults", exc_info=True)
        return dict(defaults)
