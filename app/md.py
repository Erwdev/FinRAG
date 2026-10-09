"""Koneksi MotherDuck untuk API (token baca-saja), penjaga compute, dan SQL guard (Architecture.md 4.3, 5.2, 1.2)."""

from __future__ import annotations

import datetime as dt
import math
import re
import threading
import time

import duckdb
import sqlglot
from sqlglot import exp

from app.redis_keys import md_seconds
from app.settings import get_settings

QUERY_TIMEOUT_SECONDS = 10
ROW_LIMIT = 500
ALLOWED_TABLES = {"finrag.mart.mart_ohlcv_1d", "finrag.mart.mart_indicators", "finrag.mart.mart_feed"}
BANNED_FUNC_PREFIXES = ("read_", "glob", "parquet_", "duckdb_", "pragma_", "md_")
BANNED_FUNCS = {"query", "query_table", "getenv", "current_setting", "load_extension", "install_extension"}
PATH_LIKE = re.compile(r"(s3://|gs://|https?://|file:|/)", re.IGNORECASE)


class SqlRejected(ValueError):
    pass


class MdCapExceeded(RuntimeError):
    """Batas detik compute bulanan tercapai (MD_MONTHLY_SECONDS_CAP)."""


class MdUnavailable(RuntimeError):
    """MotherDuck tidak bisa dihubungi atau query melewati batas waktu."""


def check_readonly_sql(sql: str) -> str:
    """Kembalikan SQL yang sudah dibungkus LIMIT, atau lempar SqlRejected."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as exc:
        raise SqlRejected(f"parse error: {exc}") from exc

    if len(statements) != 1:
        raise SqlRejected("exactly one statement is allowed")
    stmt = statements[0]
    if not isinstance(stmt, (exp.Select, exp.Union)):
        raise SqlRejected("only SELECT is allowed")

    cte_names = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE)}
    for node in stmt.find_all(exp.Table):
        if not isinstance(node.this, exp.Identifier):
            raise SqlRejected("table functions and path literals are not allowed")
        name = node.name.lower()
        if not node.db and not node.catalog and name in cte_names:
            continue
        full = f"{(node.catalog or 'finrag').lower()}.{(node.db or 'mart').lower()}.{name}"
        if full not in ALLOWED_TABLES:
            raise SqlRejected(f"table not allowed: {full}")

    for func in stmt.find_all(exp.Func):
        fname = func.name.lower() if isinstance(func, exp.Anonymous) else func.sql_name().lower()
        if fname in BANNED_FUNCS or fname.startswith(BANNED_FUNC_PREFIXES):
            raise SqlRejected(f"function not allowed: {fname}")

    for lit in stmt.find_all(exp.Literal):
        if lit.is_string and PATH_LIKE.search(lit.this):
            raise SqlRejected("path or URL literal is not allowed")

    wrapped = exp.select("*").from_(stmt.subquery("q")).limit(ROW_LIMIT)
    return wrapped.sql(dialect="duckdb")


_ro_conn: duckdb.DuckDBPyConnection | None = None


def ro_connection() -> duckdb.DuckDBPyConnection:
    """Koneksi tunggal per proses (dipakai ulang antar invocation hangat)."""
    global _ro_conn
    if _ro_conn is None:
        s = get_settings()
        if not s.motherduck_token_ro:
            raise MdUnavailable("MOTHERDUCK_TOKEN_RO belum diset")
        _ro_conn = duckdb.connect(
            f"md:{s.md_database}",
            config={
                "motherduck_token": s.motherduck_token_ro,
                "home_directory": "/tmp",
                # Ekstensi dipasang saat build image di /opt (Dockerfile). Tanpa unduhan saat cold start.
                "extension_directory": "/opt/duckdb_ext",
                "autoinstall_known_extensions": False,
                "autoload_known_extensions": True,
            },
        )
    return _ro_conn


def _month_key() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m")


def run_query(redis_client, sql: str, params: list | None = None) -> tuple[list[str], list[tuple]]:
    """Jalankan SELECT dengan batas waktu dan penghitung detik. Return (kolom, baris)."""
    safe_sql = check_readonly_sql(sql)
    s = get_settings()
    month = _month_key()
    used = int(redis_client.get(md_seconds(month)) or 0)
    if used >= s.md_monthly_seconds_cap:
        raise MdCapExceeded(f"md:seconds {used} >= cap {s.md_monthly_seconds_cap}")

    con = ro_connection()
    timer = threading.Timer(QUERY_TIMEOUT_SECONDS, con.interrupt)
    timer.start()
    started = time.monotonic()
    try:
        cur = con.execute(safe_sql, params or [])
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
    except duckdb.InterruptException as exc:
        raise MdUnavailable("query timeout") from exc
    except duckdb.Error as exc:
        raise MdUnavailable(str(exc)) from exc
    finally:
        timer.cancel()
        elapsed = time.monotonic() - started
        redis_client.incrby(md_seconds(month), math.ceil(elapsed))
    return cols, rows
