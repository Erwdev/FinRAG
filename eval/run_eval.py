"""Runner eval (Architecture.md 13.2): kirim pertanyaan ke API, bandingkan status terminal dengan harapan.

Hasil dipakai untuk dua hal: (1) menghitung tingkat blocked dan handoff per rail, (2) kalibrasi MIN_SIMILARITY.
Tidak menyimpan token. Token dibaca dari env EVAL_TOKEN (JWT Clerk milik user owner).

Pemakaian (setelah API hidup):
    EVAL_BASE_URL=https://xxx.lambda-url.us-east-1.on.aws EVAL_TOKEN=... uv run python -m eval.run_eval
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

import httpx

QUESTIONS = Path(__file__).with_name("questions.jsonl")
TERMINAL = {"completed", "blocked", "insufficient", "handoff", "failed", "cancelled"}
POLL_SECONDS = 2
MAX_POLLS = 90


def load_questions(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_one(client: httpx.Client, base: str, q: dict) -> str:
    resp = client.post(
        f"{base}/chat",
        json={"question": q["question"], "client_request_id": f"eval-{q['id']}-{uuid.uuid4().hex[:8]}"},
    )
    if resp.status_code != 202:
        return f"http_{resp.status_code}"
    job_id = resp.json()["job_id"]
    status = "queued"
    for _ in range(MAX_POLLS):
        time.sleep(POLL_SECONDS)
        status = client.get(f"{base}/jobs/{job_id}").json().get("status", "")
        if status in TERMINAL:
            return status
    return "timeout_poll"


def main() -> int:
    base = os.environ.get("EVAL_BASE_URL", "").rstrip("/")
    token = os.environ.get("EVAL_TOKEN", "")
    if not base or not token:
        print("set EVAL_BASE_URL dan EVAL_TOKEN", file=sys.stderr)
        return 2

    questions = load_questions(QUESTIONS)
    results = []
    with httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=30) as client:
        for q in questions:
            got = run_one(client, base, q)
            ok = got == q["expect"]
            results.append({"id": q["id"], "expect": q["expect"], "got": got, "ok": ok})
            print(f"{q['id']} expect={q['expect']} got={got} {'OK' if ok else 'MISMATCH'}")

    counts = Counter(r["got"] for r in results)
    matched = sum(r["ok"] for r in results)
    print(f"\nsesuai harapan: {matched}/{len(results)}")
    print("distribusi status:", dict(counts))
    out = Path(__file__).with_name("last_run.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"detail: {out}")
    return 0 if matched == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
