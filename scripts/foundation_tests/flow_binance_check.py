"""Binance klines check from a Prefect managed runner (its egress IP differs from local).

Run from repo root:
  prefect work-pool create finrag-managed --type prefect:managed   (once)
  prefect deploy scripts/foundation_tests/flow_binance_check.py:check_binance -n binance-ip-check -p finrag-managed
  prefect flow run --deployment binance-ip-check
Retry with the other base URL:
  prefect flow run --deployment binance-ip-check --params '{"base": "https://api.binance.com"}'
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

from prefect import flow, task


@task(retries=2, retry_delay_seconds=5)
def fetch_klines(base: str | None = None) -> tuple[int, str]:
    base = base or os.environ.get("BINANCE_BASE_URL", "https://data-api.binance.vision")
    url = f"{base.rstrip('/')}/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=2"
    req = urllib.request.Request(url, headers={"User-Agent": "FinRAG-foundation-test/1.0"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            elapsed = (time.perf_counter() - started) * 1000
            return resp.status, f"HTTP {resp.status}, {len(data)} candles, last close={data[-1][4]}, {elapsed:.0f} ms (base={base})"
    except urllib.error.HTTPError as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return exc.code, f"HTTP {exc.code}, {elapsed:.0f} ms (base={base}) - body={exc.read().decode('utf-8', 'replace')[:300]}"
    except Exception as exc:
        return 0, f"error: {exc} (base={base})"


@flow(name="binance-ip-check")
def check_binance(base: str | None = None) -> bool:
    status, detail = fetch_klines(base)
    if status == 200:
        print(f"[PASS] {detail}")
        print("RESULT: PASS")
        return True
    print(f"[FAIL] {detail}")
    if status in (403, 451):
        print("  note: IP rejected - try BINANCE_BASE_URL=https://api.binance.com or CoinGecko fallback (bagian 15)")
    print("RESULT: FAIL")
    return False


if __name__ == "__main__":
    sys.exit(0 if check_binance() else 1)
