"""Klien LLM tunggal lewat Cloudflare AI Gateway (Architecture.md 6.1, 6.3). Tidak ada panggilan penyedia langsung."""

from __future__ import annotations

from app.settings import get_settings


class LlmNotConfigured(RuntimeError):
    pass


def make_chat_model(model: str):
    """ChatOpenAI dengan basis URL gateway. Impor LangChain lazy agar cold start ringan."""
    from langchain_openai import ChatOpenAI

    s = get_settings()
    if not s.llm_base_url or not s.cf_aig_token:
        raise LlmNotConfigured("LLM_BASE_URL dan CF_AIG_TOKEN wajib diset")
    return ChatOpenAI(
        base_url=s.llm_base_url,
        api_key=s.llm_api_key or "unused",  # kunci penyedia disimpan di Cloudflare
        default_headers={"cf-aig-authorization": f"Bearer {s.cf_aig_token}"},
        model=model,
        temperature=0,
        max_retries=1,
        timeout=60,
    )


def with_fallback(primary, fallback_model: str | None):
    """Pengaman terakhir di aplikasi. Aturan utama ada di gateway (bagian 6.1)."""
    if not fallback_model:
        return primary
    return primary.with_fallbacks([make_chat_model(fallback_model)])
