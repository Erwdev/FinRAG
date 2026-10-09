"""dlt resource raw_articles: satu RSS berita (NEWS_RSS_URL), cocokkan alias per ticker (bagian 4.4)."""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone

import dlt
import feedparser

from app.domain.market.universe import load_universe

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _clean(text: str | None) -> str:
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", text or ""))).strip()


def match_tickers(text: str) -> list[str]:
    lower = text.lower()
    found = []
    for coin in load_universe():
        for alias in coin["news_aliases"]:
            if re.search(rf"\b{re.escape(alias.lower())}\b", lower):
                found.append(coin["symbol"])
                break
    return found


@dlt.resource(
    name="raw_articles",
    write_disposition="append",
    primary_key="article_id",
    max_table_nesting=0,
    # Teks: kolom boleh bertambah (evolve), sesuai Architecture.md 4.2.
    schema_contract={"columns": "evolve"},
)
def raw_articles(feed_url: str):
    parsed = feedparser.parse(feed_url)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"RSS tidak dapat dibaca: {feed_url}")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []
    for entry in parsed.entries:
        url = entry.get("link")
        if not url:
            continue
        title = _clean(entry.get("title"))
        summary = _clean(entry.get("summary"))
        tickers = match_tickers(f"{title} {summary}")
        if not tickers:
            continue  # hanya artikel yang menyebut koin di universe
        parsed_time = entry.get("published_parsed")
        published = (
            datetime(*parsed_time[:6], tzinfo=timezone.utc).replace(tzinfo=None) if parsed_time else now
        )
        rows.append(
            {
                "article_id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:32],
                "url": url,
                "title": title[:500],
                "summary": summary[:2000],
                "published_at": published,
                "source": "rss",
                "tickers_json": json.dumps(tickers),
            }
        )
    if rows:
        yield rows
