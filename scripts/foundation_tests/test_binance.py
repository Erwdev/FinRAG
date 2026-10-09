"""Binance klines connectivity test (local / Cloud Run / Prefect runner).

Env: BINANCE_BASE_URL (default https://data-api.binance.vision)
Usage: python scripts/foundation_tests/test_binance.py [--base https://api.binance.com]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASES = [
    os.environ.get("BINANCE_BASE_URL", "https://data-api.binance.vision"),
    "https://api.binance.com",
]


def fetch_klines(base: str, symbol: str, interval: str, limit: int) -> tuple[int, list, float]:
    url = f"{base.rstrip('/')}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "FinRAG-foundation-test/1.0"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()
            elapsed = (time.perf_counter() - started) * 1000
            return resp.status, json.loads(body), elapsed
    except urllib.error.HTTPError as exc:
        elapsed = (time.perf_counter() - started) * 1000
        body = exc.read().decode("utf-8", "replace")
        return exc.code, [{"error": body}], elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Override BINANCE_BASE_URL for this run")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()

    bases = [args.base] if args.base else DEFAULT_BASES
    ok = False
    for base in bases:
        status, data, elapsed_ms = fetch_klines(base, args.symbol, args.interval, args.limit)
        label = f"{base} {args.symbol} {args.interval}"
        if status == 200 and isinstance(data, list) and data:
            last_close = data[-1][4]
            print(f"[PASS] {label}: HTTP 200, {len(data)} candles, last close={last_close}, {elapsed_ms:.0f} ms")
            ok = True
            break
        if status in (403, 451):
            print(f"[BLOCKED] {label}: HTTP {status} - IP rejected (region/compliance block, bagian 1.1)")
        else:
            print(f"[FAIL] {label}: HTTP {status}, {elapsed_ms:.0f} ms, body={data}")
    if not ok:
        print("RESULT: FAIL - try the other base URL; if both fail, enable CoinGecko fallback (bagian 15)")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
