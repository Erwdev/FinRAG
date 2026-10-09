"""Nama kunci dan event Redis (Architecture.md 8.1 dan 8.3). Satu sumber untuk API dan flows."""

EVENTS_SYSTEM = "events:system"  # list, LTRIM ke 200 entri terakhir
SIGNALS_LATEST = "signals:latest"  # TTL 5 menit
PRICE_LIVE = "price:live"  # TTL 15 detik
X_BUCKET = "x:bucket"  # SET NX EX 900
X_DUE = "x:due"  # sorted set, rotasi scrape X
FC_USED_TOTAL = "fc:used:total"  # kredit Firecrawl terpakai (sekali pakai, tanpa TTL)


def freshness(source: str) -> str:
    """source: prices, news, x, build."""
    return f"freshness:{source}"


def flow_lock(name: str) -> str:
    return f"lock:flow:{name}"


def chart(ticker: str, rng: str) -> str:
    return f"chart:{ticker}:{rng}"


def feed(ticker: str, limit: int) -> str:
    return f"feed:text:{ticker}:{limit}"


def md_seconds(yyyymm: str) -> str:
    """Counter detik query MotherDuck dari aplikasi (penjaga 10 jam compute)."""
    return f"md:seconds:{yyyymm}"


def embed_tokens(yyyymm: str) -> str:
    """Counter taksiran token embedding bulanan (karakter dibagi 4)."""
    return f"embed:tokens:{yyyymm}"


# --- Job chat (Architecture.md 8.1) ---
JOB_TTL_SECONDS = 7 * 24 * 3600
CANCEL_TTL_SECONDS = 3600
IDEM_TTL_SECONDS = 600


def job(job_id: str) -> str:
    """Hash status job."""
    return f"job:{job_id}"


def job_events(job_id: str) -> str:
    """List event JSON berurutan (RPUSH, seq = panjang list setelah push)."""
    return f"job:{job_id}:events"


def job_cancel(job_id: str) -> str:
    return f"job:{job_id}:cancel"


def idem_chat(user_id: str, client_request_id: str) -> str:
    return f"idem:chat:{user_id}:{client_request_id}"


def rl_chat(user_id: str, yyyymmddhh: str) -> str:
    """Maksimum 20 chat per jam (rl:chat)."""
    return f"rl:chat:{user_id}:{yyyymmddhh}"


def cost_llm(yyyymmdd: str) -> str:
    """Biaya LLM harian dalam mikro-dolar (bagian 8.1)."""
    return f"cost:llm:{yyyymmdd}"


def rl_brief(user_id: str, yyyymmdd: str) -> str:
    """Jumlah force daily brief per hari (maksimum 3)."""
    return f"rl:brief:{user_id}:{yyyymmdd}"
