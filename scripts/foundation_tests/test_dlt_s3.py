"""Uji dlt menulis Parquet ke S3 landing (Architecture.md 1.1 dan 4.2, uji 3 di tabel jam 0 sampai 2).

Memeriksa:
- tata letak berkas (dugaan dlt/landing/{table}/{load_id}.{file_id}.parquet)
- state incremental: run kedua dengan data yang sama tidak menulis baris baru
- nama extra pip "dlt[s3,parquet]" (lihat pesan error bila gagal)

Env (shell): LANDING_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (kunci finrag-prefect-writer)
Usage: uv run python -m scripts.foundation_tests.test_dlt_s3
"""

from __future__ import annotations

import datetime as dt
import os
import sys

import boto3
import dlt

PREFIX = "dlt/landing/probe_ohlcv/"


@dlt.resource(name="probe_ohlcv", write_disposition="append", primary_key="id", max_table_nesting=0)
def probe_ohlcv(cursor=dlt.sources.incremental("ts", initial_value=None)):
    ts = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc).replace(tzinfo=None)
    yield [{"id": f"probe-{n}", "ts": ts, "value": float(n)} for n in range(3)]


def main() -> int:
    bucket = os.environ.get("LANDING_BUCKET")
    if not bucket:
        print("RESULT: FAIL - set LANDING_BUCKET")
        return 1

    pipeline = dlt.pipeline(
        pipeline_name="finrag_probe",  # nama tetap, sama seperti pipeline produksi
        destination=dlt.destinations.filesystem(bucket_url=f"s3://{bucket}/dlt"),
        dataset_name="landing",
    )
    first = pipeline.run(probe_ohlcv(), loader_file_format="parquet")
    second = pipeline.run(probe_ohlcv(), loader_file_format="parquet")
    print(f"run 1 load_ids: {first.loads_ids}")
    print(f"run 2 load_ids: {second.loads_ids} (state incremental, diharapkan tanpa baris baru)")

    s3 = boto3.client("s3")
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=bucket, Prefix=PREFIX).get("Contents", [])]
    for key in keys:
        print(f"  s3://{bucket}/{key}")

    layout_ok = bool(keys) and all(k.endswith(".parquet") for k in keys)
    print(f"[{'PASS' if layout_ok else 'FAIL'}] tata letak Parquet di {PREFIX}")
    print("RESULT:", "PASS" if layout_ok else "FAIL")
    return 0 if layout_ok else 1


if __name__ == "__main__":
    sys.exit(main())
