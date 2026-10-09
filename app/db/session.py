"""Koneksi Neon (Architecture.md 3.1 dan 7).

- Driver asyncpg, NullPool, statement_cache_size=0 (pooler Neon mode transaksi).
- Parameter sslmode dan channel_binding dari URL Neon diterjemahkan ke connect_args,
  karena asyncpg tidak menerima keduanya sebagai query string.
"""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.settings import get_settings


def normalize_url(raw: str) -> tuple[URL, dict]:
    url = make_url(raw)
    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)

    connect_args: dict = {"statement_cache_size": 0}
    if sslmode in ("require", "verify-ca", "verify-full"):
        connect_args["ssl"] = True

    url = url.set(drivername="postgresql+asyncpg", query=query)
    return url, connect_args


def make_engine(raw_url: str) -> AsyncEngine:
    url, connect_args = normalize_url(raw_url)
    return create_async_engine(url, poolclass=NullPool, connect_args=connect_args)


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return make_engine(get_settings().database_url)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
