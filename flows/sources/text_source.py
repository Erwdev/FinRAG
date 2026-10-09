"""TextSource: sumber teks X lewat Firecrawl (Architecture.md 4.5 aturan 7 dan 14.2).

Interface dipisah agar sumber dapat diganti (mis. berita saja) tanpa mengubah arsitektur.
Parsing hasil scrape bersifat heuristik dan wajib diuji di blok 0 sampai 2 (lihat backlog.md).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Protocol
from urllib.parse import quote

import httpx

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
X_SEARCH_URL = "https://x.com/search?q={q}&f=live"
MIN_BLOCK_CHARS = 40
MAX_TEXT_CHARS = 500
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


class TextSource(Protocol):
    def search(self, query: str, ticker: str, limit: int = 20) -> tuple[list[dict], int]:
        """Return (item, kredit terpakai). Item: tweet_id, text, author, created_at, ticker_query, url."""
        ...


def parse_posts(markdown: str, url: str, ticker: str, limit: int) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    items: list[dict] = []
    seen: set[str] = set()
    for block in re.split(r"\n\s*\n", markdown):
        text = _LINK.sub(r"\1", block).strip()
        text = re.sub(r"\s+", " ", text)
        if len(text) < MIN_BLOCK_CHARS:
            continue
        tweet_id = hashlib.sha256(f"{url}|{text}".encode("utf-8")).hexdigest()[:32]
        if tweet_id in seen:
            continue
        seen.add(tweet_id)
        items.append(
            {
                "tweet_id": tweet_id,
                "text": text[:MAX_TEXT_CHARS],
                "author": None,
                # Waktu posting belum diekstrak dari halaman; memakai waktu scrape (lihat backlog.md).
                "created_at": now,
                "ticker_query": ticker,
                "url": url,
            }
        )
        if len(items) >= limit:
            break
    return items


class FirecrawlXSource:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, ticker: str, limit: int = 20) -> tuple[list[dict], int]:
        url = X_SEARCH_URL.format(q=quote(query))
        resp = httpx.post(
            FIRECRAWL_SCRAPE_URL,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"url": url, "onlyMainContent": True},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"firecrawl error: {data.get('error', 'unknown')}")
        credits = int(data.get("creditsUsed") or 1)
        markdown = (data.get("data") or {}).get("markdown") or ""
        return parse_posts(markdown, url, ticker, limit), credits
