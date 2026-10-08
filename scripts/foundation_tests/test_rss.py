"""News RSS connectivity test (RSS 2.0, Atom, or RDF).

Env: NEWS_RSS_URL
Usage: python scripts/foundation_tests/test_rss.py [feed_url]
"""
import os
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_items(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for node in root.iter():
        name = local_name(node.tag)
        if name in ("item", "entry"):
            fields = {}
            for child in node:
                fields[local_name(child.tag)] = (child.text or "").strip()
            if fields:
                items.append(fields)
    return items


def pick_title(item: dict) -> str:
    for key in ("title", "link", "guid", "id"):
        if item.get(key):
            return item[key][:120]
    return "(no title)"


def pick_date(item: dict) -> str:
    for key in ("pubDate", "published", "updated", "date"):
        if item.get(key):
            return item[key]
    return "(no date)"


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("NEWS_RSS_URL", "")
    if not url:
        print("RESULT: FAIL - provide a feed URL argument or set NEWS_RSS_URL")
        return 1

    req = urllib.request.Request(url, headers={"User-Agent": "FinRAG-foundation-test/1.0"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        print(f"[FAIL] {url}: HTTP {exc.code}")
        print("RESULT: FAIL")
        return 1
    except Exception as exc:
        print(f"[FAIL] {url}: {exc}")
        print("RESULT: FAIL")
        return 1
    elapsed_ms = (time.perf_counter() - started) * 1000

    if status != 200:
        print(f"[FAIL] {url}: HTTP {status}")
        print("RESULT: FAIL")
        return 1

    try:
        items = parse_items(body)
    except ET.ParseError as exc:
        print(f"[FAIL] {url}: not valid XML ({exc})")
        print("RESULT: FAIL")
        return 1

    if not items:
        print(f"[FAIL] {url}: XML parsed but 0 items found")
        print("RESULT: FAIL")
        return 1

    newest = items[0]
    print(f"[PASS] {url}: {len(items)} items, {len(body)} bytes, {elapsed_ms:.0f} ms")
    print(f"  newest: {pick_title(newest)} | {pick_date(newest)}")
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
