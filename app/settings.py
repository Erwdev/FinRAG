"""Konfigurasi API (Architecture.md 11.7).

Rahasia Lambda ada di SSM Parameter Store (SecureString). Saat cold start, parameter di bawah
SSM_PATH dimuat ke os.environ (sekali per proses). Nilai yang sudah ada di env tidak ditimpa.
"""

import logging
import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


def load_ssm_into_env(path: str | None) -> int:
    """Muat semua parameter di bawah path ke os.environ. Return jumlah parameter yang dimuat."""
    if not path:
        return 0
    import boto3  # lazy: tidak dimuat saat tes lokal tanpa SSM

    client = boto3.client("ssm")
    loaded = 0
    paginator = client.get_paginator("get_parameters_by_path")
    for page in paginator.paginate(Path=path, Recursive=False, WithDecryption=True):
        for param in page["Parameters"]:
            name = param["Name"].rsplit("/", 1)[-1]
            if name not in os.environ:
                os.environ[name] = param["Value"]
                loaded += 1
    log.info("ssm: loaded %d parameters from %s", loaded, path)
    return loaded


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    # Auth
    clerk_jwks_url: str
    clerk_issuer: str
    allowed_origins: str = "http://localhost:3000"

    # Postgres (Neon, pooler)
    database_url: str

    # Konfigurasi AWS (non-rahasia, diisi Terraform)
    ssm_path: str | None = None
    sqs_queue_url: str | None = None
    landing_bucket: str | None = None

    # MotherDuck (token RO dipakai API dan worker, bagian 3.4)
    md_database: str = "finrag"
    md_monthly_seconds_cap: int = 28800
    motherduck_token_ro: str | None = None

    # Redis (Upstash, bagian 8)
    upstash_redis_rest_url: str | None = None
    upstash_redis_rest_token: str | None = None

    # Sumber harga (bagian 4.5)
    binance_base_url: str = "https://data-api.binance.vision"
    coingecko_api_key: str | None = None

    # Observabilitas (kosong = nonaktif)
    sentry_dsn: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://us.cloud.langfuse.com"

    # LLM lewat Cloudflare AI Gateway saja (bagian 6.1)
    llm_base_url: str | None = None
    cf_aig_token: str | None = None
    llm_api_key: str = "unused"  # kosong bila kunci penyedia disimpan di Cloudflare
    planner_model: str = "deepseek-v4.1-flash"
    final_model: str = "qwen3.7-plus"
    fallback_model: str | None = None
    daily_llm_budget_usd: float = 1.0

    # Retrieval (bagian 5.3)
    pinecone_api_key: str | None = None
    pinecone_index: str = "finrag-text"
    embedding_model: str = "multilingual-e5-large"
    embedding_dim: int = 1024

    # Notifikasi handoff (bagian 6.6, opsional)
    handoff_webhook_url: str | None = None

    @property
    def allowed_origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_ssm_into_env(os.environ.get("SSM_PATH"))
    return Settings()  # type: ignore[call-arg]
