"""Kunci Redis domain chat (Architecture.md 8.1). Job, idempotensi, rate limit, dan biaya LLM."""

# --- Job chat ---
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


def idem_brief(user_id: str, client_request_id: str) -> str:
    return f"idem:brief:{user_id}:{client_request_id}"


def rl_chat(user_id: str, yyyymmddhh: str) -> str:
    """Maksimum 20 chat per jam (rl:chat)."""
    return f"rl:chat:{user_id}:{yyyymmddhh}"


def rl_brief(user_id: str, yyyymmdd: str) -> str:
    """Jumlah force daily brief per hari (maksimum 3)."""
    return f"rl:brief:{user_id}:{yyyymmdd}"


def cost_llm(yyyymmdd: str) -> str:
    """Biaya LLM harian dalam mikro-dolar (bagian 8.1)."""
    return f"cost:llm:{yyyymmdd}"
