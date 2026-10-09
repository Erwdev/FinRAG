"""Inisialisasi MotherDuck (Architecture.md 3.3 dan 4.3). Idempoten, aman dijalankan ulang.

Membuat database finrag, skema raw/stg/mart, tabel raw (dbt/ddl/raw.sql), dan secret persisten
finrag_landing untuk membaca S3 landing (kunci finrag-md-reader, bagian 3.4).

Env dari shell (tidak dari berkas .env, tidak pernah dicetak):
  MOTHERDUCK_TOKEN_RW             token baca-tulis (sa-md-flows)
  LANDING_BUCKET                  nama bucket landing
  MD_READER_AWS_ACCESS_KEY_ID     kunci finrag-md-reader
  MD_READER_AWS_SECRET_ACCESS_KEY secret finrag-md-reader
  AWS_REGION                      default us-east-1

Usage (akar repositori): uv run python -m scripts.init_motherduck
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DDL = ROOT / "dbt" / "ddl" / "raw.sql"


def _req(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} belum diset di environment shell")
    return value


def _q(value: str) -> str:
    """Escape literal SQL string. Dipakai hanya untuk nilai dari environment."""
    return "'" + value.replace("'", "''") + "'"


def main() -> int:
    token = _req("MOTHERDUCK_TOKEN_RW")
    bucket = _req("LANDING_BUCKET")
    key_id = _req("MD_READER_AWS_ACCESS_KEY_ID")
    secret = _req("MD_READER_AWS_SECRET_ACCESS_KEY")
    region = os.environ.get("AWS_REGION", "us-east-1")

    con = duckdb.connect("md:", config={"motherduck_token": token})
    con.execute("CREATE DATABASE IF NOT EXISTS finrag")
    con.execute("USE finrag")
    con.execute("CREATE SCHEMA IF NOT EXISTS stg")
    con.execute("CREATE SCHEMA IF NOT EXISTS mart")

    for stmt in DDL.read_text(encoding="utf-8").split(";"):
        body = "\n".join(line for line in stmt.splitlines() if not line.strip().startswith("--")).strip()
        if body:
            con.execute(body)

    con.execute(
        "CREATE OR REPLACE PERSISTENT SECRET finrag_landing ("
        f"TYPE s3, KEY_ID {_q(key_id)}, SECRET {_q(secret)}, REGION {_q(region)})"
    )

    tables = [r[0] for r in con.execute("SELECT table_schema || '.' || table_name FROM information_schema.tables WHERE table_schema IN ('raw','stg','mart') ORDER BY 1").fetchall()]
    print(f"OK: database finrag siap. Tabel: {tables}")
    print(f"OK: persistent secret finrag_landing dibuat untuk bucket {bucket} (nilai kunci tidak dicetak)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
