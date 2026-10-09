import datetime as dt

from fastapi import APIRouter, Depends

from app.auth.deps import CurrentUser, get_current_owner
from app.clock import utc_now_iso
from app.infra.redis import get_redis, read_fresh

router = APIRouter()
SOURCES = ("prices", "news", "x", "build")


@router.get("/status/freshness")
def freshness(_: CurrentUser = Depends(get_current_owner)) -> dict:
    rd = get_redis()
    now = dt.datetime.now(dt.timezone.utc)
    out = {}
    for src in SOURCES:
        ts = read_fresh(rd, src)
        age = None
        if ts:
            parsed = dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
            age = int((now - parsed).total_seconds())
        out[src] = {"last_success": ts, "age_seconds": age}
    return {"sources": out, "now": utc_now_iso()}
