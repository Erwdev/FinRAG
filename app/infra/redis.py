"""Klien Upstash Redis (REST) dan helper kecil untuk JSON, event sistem, dan freshness."""

import json
from functools import lru_cache

from upstash_redis import Redis

from app.clock import utc_now_iso
from app.settings import get_settings

EVENTS_SYSTEM = "events:system"  # list, LTRIM ke 200 entri terakhir


def freshness(source: str) -> str:
    """source: prices, news, x, build."""
    return f"freshness:{source}"


def flow_lock(name: str) -> str:
    return f"lock:flow:{name}"


def make_redis(url: str, token: str) -> Redis:
    return Redis(url=url, token=token)


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    s = get_settings()
    if not s.upstash_redis_rest_url or not s.upstash_redis_rest_token:
        raise RuntimeError("UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN belum diset")
    return make_redis(s.upstash_redis_rest_url, s.upstash_redis_rest_token)


def get_json(r: Redis, key: str):
    raw = r.get(key)
    return json.loads(raw) if raw else None


def set_json(r: Redis, key: str, value, ttl_seconds: int) -> None:
    r.set(key, json.dumps(value, default=str), ex=ttl_seconds)


def push_event(r: Redis, event_type: str, message: str, **data) -> None:
    payload = {"ts": utc_now_iso(), "type": event_type, "message": message, "data": data}
    r.rpush(EVENTS_SYSTEM, json.dumps(payload, default=str))
    r.ltrim(EVENTS_SYSTEM, -200, -1)


def mark_fresh(r: Redis, source: str) -> None:
    r.set(freshness(source), utc_now_iso())


def read_fresh(r: Redis, source: str) -> str | None:
    value = r.get(freshness(source))
    return value if value else None
