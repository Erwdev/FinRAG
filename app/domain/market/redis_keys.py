"""Kunci Redis domain market (Architecture.md 8.1 dan 8.3). Harga, sinyal, grafik, feed, dan ingest."""

SIGNALS_LATEST = "signals:latest"  # TTL 5 menit
PRICE_LIVE = "price:live"  # TTL 15 detik
X_BUCKET = "x:bucket"  # SET NX EX 900
X_DUE = "x:due"  # sorted set, rotasi scrape X
FC_USED_TOTAL = "fc:used:total"  # kredit Firecrawl terpakai (sekali pakai, tanpa TTL)


def chart(ticker: str, rng: str) -> str:
    return f"chart:{ticker}:{rng}"


def feed(ticker: str, limit: int) -> str:
    return f"feed:text:{ticker}:{limit}"


def embed_tokens(yyyymm: str) -> str:
    """Counter taksiran token embedding bulanan (karakter dibagi 4)."""
    return f"embed:tokens:{yyyymm}"
