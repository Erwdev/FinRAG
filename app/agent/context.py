"""Context builder (Architecture.md 5.2, 6.2): indikator YAML, portofolio YAML, evidence XML."""

from __future__ import annotations

import datetime as dt
from xml.sax.saxutils import escape

import yaml

from app.agent.prompts import evidence_item


def _num(x):
    """Angka dengan titik desimal, tanpa pemisah ribuan. None tetap None."""
    if x is None:
        return None
    if isinstance(x, float):
        return round(x, 8)
    return x


def indicators_yaml(rows: list[dict]) -> str:
    items = []
    for r in rows:
        items.append(
            {
                "ticker": r["ticker"],
                "as_of": r["as_of"],
                "close": _num(r.get("close")),
                "sma20": _num(r.get("sma20")),
                "sma50": _num(r.get("sma50")),
                "sma200": _num(r.get("sma200")),
                "ema12": _num(r.get("ema12")),
                "ema26": _num(r.get("ema26")),
                "roc20_pct": _num(r.get("roc20_pct")),
                "stdev20_pct": _num(r.get("stdev20_pct")),
                "bollinger20_2": {
                    "lower": _num(r.get("bb_lower")),
                    "upper": _num(r.get("bb_upper")),
                    "band_pos": _num(r.get("band_pos")),
                },
                "drawdown_252_pct": _num(r.get("drawdown_252_pct")),
            }
        )
    return yaml.safe_dump(items, sort_keys=False, allow_unicode=True) if items else "[]"


def portfolio_yaml(positions: list[dict]) -> str:
    items = [
        {
            "ticker": p["ticker"],
            "quantity": _num(p["quantity"]),
            "avg_cost": _num(p.get("avg_cost")),
            "last_price": _num(p.get("last_price")),
            "value": _num(p.get("value")),
            "weight_pct": _num(p.get("weight_pct")),
        }
        for p in positions
    ]
    return yaml.safe_dump(items, sort_keys=False, allow_unicode=True) if items else "[]"


def evidence_blocks(chunks: list[dict], now: dt.datetime) -> list[dict]:
    """Ubah chunk hasil rerank menjadi item XML dan daftar evidence untuk disimpan di result.

    Return list dict: {id, ticker, source_type, url, published_at, snippet, score, xml}.
    """
    out = []
    for c in chunks:
        md = c["metadata"]
        published = dt.datetime.fromtimestamp(md["published_at_ts"], tz=dt.timezone.utc)
        iso = published.strftime("%Y-%m-%dT%H:%M:%SZ")
        age = c.get("age_hours", max((now - published).total_seconds() / 3600.0, 0.0))
        text = md.get("text", "")
        # Teks dari internet tidak tepercaya: di-escape agar tidak bisa menutup tag <item> sendiri.
        out.append(
            {
                "id": c["id"],
                "ticker": md["ticker"],
                "source_type": md["source_type"],
                "url": md.get("url", ""),
                "published_at": iso,
                "snippet": text[:280],
                "score": round(c.get("score_final", c["score"]), 4),
                "xml": evidence_item(
                    c["id"], md["ticker"], md["source_type"], iso, age, escape(text, {'"': "&quot;"})
                ),
            }
        )
    return out


def render_evidence(evidence: list[dict]) -> str:
    return "\n".join(e["xml"] for e in evidence)
