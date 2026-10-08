"""Firecrawl scrape test against an X search page (bagian 5.3, risiko PL-1).

Env: FIRECRAWL_API_KEY
Usage: python scripts/foundation_tests/test_firecrawl_x.py [--url "https://x.com/search?q=%24BTC&f=live"]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API_URL = "https://api.firecrawl.dev/v1/scrape"
DEFAULT_X_URL = "https://x.com/search?q=%24BTC&f=live"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_X_URL, help="X search URL to scrape")
    args = parser.parse_args()

    api_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not api_key:
        print("RESULT: FAIL - set FIRECRAWL_API_KEY")
        return 1

    payload = json.dumps({"url": args.url, "onlyMainContent": True}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "FinRAG-foundation-test/1.0",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
    elapsed_ms = (time.perf_counter() - started) * 1000

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(f"[FAIL] HTTP {status}: non-JSON body: {body[:300]!r}")
        print("RESULT: FAIL")
        return 1

    success = bool(data.get("success"))
    credits = data.get("creditsUsed", data.get("credits_used", "?"))
    doc_len = 0
    doc = (data.get("data") or {}).get("markdown") or ""
    doc_len = len(doc)

    if status == 200 and success and doc_len > 0:
        print(f"[PASS] {args.url}: HTTP 200, markdown {doc_len} chars, creditsUsed={credits}, {elapsed_ms:.0f} ms")
        print(f"  first 200 chars: {doc[:200]!r}")
        print("RESULT: PASS")
        return 0

    error = data.get("error", data.get("message", "unknown"))
    print(f"[FAIL] {args.url}: HTTP {status}, success={success}, creditsUsed={credits}, error={error}")
    if doc_len == 0 and success:
        print("  note: empty markdown - X likely demanded login (risiko bagian 15); activate TextSource fallback")
    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
