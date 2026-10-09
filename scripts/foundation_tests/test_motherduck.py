"""Uji MotherDuck (Architecture.md 13 jam 0 sampai 2, tabel "Foundation Test Log" test 2, 6, 7, 8).

Bagian A  RW token membaca S3 privat lewat secret persisten finrag_landing.
Bagian B  Ekstensi motherduck dimuat dari extension_directory (jalankan di dalam image Lambda untuk uji 6).
Bagian C  Token baca-saja (RO) tidak bisa menulis.
Bagian D  enable_external_access=false pada koneksi md: (uji 8).

Env (shell): MOTHERDUCK_TOKEN_RW, MOTHERDUCK_TOKEN_RO, LANDING_BUCKET
Usage:
  uv run python -m scripts.foundation_tests.test_motherduck
  uv run python -m scripts.foundation_tests.test_motherduck --ext-only   (di dalam image Lambda)
"""

from __future__ import annotations

import argparse
import os
import sys

import duckdb


def _result(name: str, ok: bool | None, detail: str) -> bool:
    tag = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
    print(f"[{tag}] {name}: {detail}")
    return ok is not False


def check_ext_only() -> bool:
    ext_dir = os.environ.get("DUCKDB_EXTENSION_DIR", "/opt/duckdb_ext")
    con = duckdb.connect(config={"home_directory": "/tmp", "extension_directory": ext_dir,
                                 "autoinstall_known_extensions": False, "autoload_known_extensions": True})
    try:
        con.execute("LOAD motherduck")
        version = con.execute("SELECT version()").fetchone()[0]
        return _result("ekstensi motherduck dimuat tanpa unduhan", True, f"duckdb {version}, dir={ext_dir}")
    except duckdb.Error as exc:
        return _result("ekstensi motherduck dimuat tanpa unduhan", False, str(exc))


def check_rw_reads_s3() -> bool:
    bucket = os.environ.get("LANDING_BUCKET")
    token = os.environ.get("MOTHERDUCK_TOKEN_RW")
    if not bucket or not token:
        return _result("RW membaca S3 privat via secret", None, "set LANDING_BUCKET dan MOTHERDUCK_TOKEN_RW")
    con = duckdb.connect("md:finrag", config={"motherduck_token": token, "home_directory": "/tmp"})
    try:
        count = con.execute(
            f"SELECT count(*) FROM read_parquet('s3://{bucket}/dlt/landing/raw_ohlcv/*.parquet')"
        ).fetchone()[0]
        return _result("RW membaca S3 privat via secret", True, f"{count} baris dari raw_ohlcv Parquet")
    except duckdb.Error as exc:
        msg = str(exc)
        if "No files found" in msg:
            return _result("RW membaca S3 privat via secret", None, "belum ada berkas Parquet (jalankan dlt dulu)")
        return _result("RW membaca S3 privat via secret", False, msg)
    finally:
        con.close()


def check_ro_cannot_write() -> bool:
    token = os.environ.get("MOTHERDUCK_TOKEN_RO")
    if not token:
        return _result("RO tidak bisa menulis", None, "set MOTHERDUCK_TOKEN_RO")
    con = duckdb.connect("md:finrag", config={"motherduck_token": token, "home_directory": "/tmp"})
    try:
        con.execute("CREATE TABLE IF NOT EXISTS mart.probe_should_fail (x INTEGER)")
        con.execute("DROP TABLE IF EXISTS mart.probe_should_fail")
        return _result("RO tidak bisa menulis", False, "CREATE TABLE berhasil. Token RO terlalu luas")
    except duckdb.Error as exc:
        return _result("RO tidak bisa menulis", True, f"ditolak: {str(exc)[:120]}")
    finally:
        con.close()


def check_external_access_flag() -> bool:
    token = os.environ.get("MOTHERDUCK_TOKEN_RO")
    if not token:
        return _result("enable_external_access=false", None, "set MOTHERDUCK_TOKEN_RO")
    con = duckdb.connect("md:finrag", config={"motherduck_token": token, "home_directory": "/tmp"})
    try:
        con.execute("SET enable_external_access = false")
        con.execute("SELECT 1").fetchone()
        return _result("enable_external_access=false", True, "dapat diset dan query sederhana tetap jalan")
    except duckdb.Error as exc:
        return _result("enable_external_access=false", False, str(exc)[:200])
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ext-only", action="store_true", help="hanya uji pemuatan ekstensi (dalam Lambda)")
    args = parser.parse_args()

    if args.ext_only:
        return 0 if check_ext_only() else 1

    checks = [check_rw_reads_s3, check_ro_cannot_write, check_external_access_flag]
    results = [fn() for fn in checks]
    print("RESULT:", "PASS" if all(results) else "FAIL")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
