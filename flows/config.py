"""Helper bersama untuk flow Prefect: rahasia, klien Redis, lock flow, dan koneksi MotherDuck RW.

Rahasia flows ada di Prefect Secret block (bagian 3.3). Nama block = nama env huruf kecil dengan
tanda hubung, contoh MOTHERDUCK_TOKEN_RW -> block "motherduck-token-rw". Nilai non-rahasia
(LANDING_BUCKET, NEWS_RSS_URL, dll.) diisi lewat job_variables.env di prefect.yaml.
"""

from __future__ import annotations

import contextlib
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.cache import make_redis  # noqa: E402
from app.redis_keys import flow_lock  # noqa: E402

SECRET_ENV_NAMES = (
    "MOTHERDUCK_TOKEN_RW",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "FIRECRAWL_API_KEY",
    "PINECONE_API_KEY",
    "COINGECKO_API_KEY",
)


def load_secrets() -> None:
    """Isi env dari Prefect Secret block. Block yang belum dibuat dilewati (env lokal tetap dipakai)."""
    from prefect.blocks.system import Secret

    for name in SECRET_ENV_NAMES:
        if os.environ.get(name):
            continue
        try:
            os.environ[name] = Secret.load(name.lower().replace("_", "-")).get()
        except ValueError:
            pass


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} belum diset (Prefect Secret block atau job_variables.env)")
    return value


def redis_client():
    return make_redis(require_env("UPSTASH_REDIS_REST_URL"), require_env("UPSTASH_REDIS_REST_TOKEN"))


@contextlib.contextmanager
def single_run_lock(r, name: str, ttl_seconds: int = 1800):
    """Kunci anti-tumpang-tindih (bagian 8.1). Yield True bila kunci didapat."""
    key = flow_lock(name)
    token = uuid.uuid4().hex
    if not r.set(key, token, nx=True, ex=ttl_seconds):
        yield False
        return
    try:
        yield True
    finally:
        if r.get(key) == token:
            r.delete(key)


def md_rw_connection(database: str = "finrag"):
    import duckdb

    return duckdb.connect(
        f"md:{database}",
        config={"motherduck_token": require_env("MOTHERDUCK_TOKEN_RW"), "home_directory": "/tmp"},
    )


def dbt_dir() -> Path:
    return ROOT / "dbt"
