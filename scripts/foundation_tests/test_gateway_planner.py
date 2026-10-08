"""One planner-style LLM call through Cloudflare AI Gateway (custom provider).

Env:
  LLM_BASE_URL    gateway base URL (SDK style, no /chat/completions suffix)
                  e.g. https://gateway.ai.cloudflare.com/v1/{account}/{gateway}/custom-opencode/v1
  CF_AIG_TOKEN    gateway auth token -> header cf-aig-authorization (if gateway auth enabled)
  LLM_API_KEY     provider key -> Authorization header (leave empty if key stored in Cloudflare)
  PLANNER_MODEL   e.g. custom-opencode/MODEL_NAME (unified API) or MODEL_NAME (provider-specific)
Usage: python scripts/foundation_tests/test_gateway_planner.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    model = os.environ.get("PLANNER_MODEL", "")
    if not base:
        print("RESULT: FAIL - set LLM_BASE_URL")
        return 1
    if not model:
        print("RESULT: FAIL - set PLANNER_MODEL")
        return 1

    if not base.endswith("/chat/completions"):
        endpoint = f"{base}/chat/completions"
    else:
        endpoint = base

    headers = {"Content-Type": "application/json"}
    token = os.environ.get("CF_AIG_TOKEN", "")
    provider_key = os.environ.get("LLM_API_KEY", "")
    if token:
        headers["cf-aig-authorization"] = f"Bearer {token}"
    if provider_key:
        headers["Authorization"] = f"Bearer {provider_key}"

    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 300,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a retrieval planner. Reply with a short JSON plan only.",
                },
                {
                    "role": "user",
                    "content": "Plan retrieval for: BTC performance this week. "
                    "Return JSON with tickers, time window, and data sources.",
                },
            ],
        }
    ).encode("utf-8")

    print(f"POST {endpoint}")
    print(f"model={model} gateway_auth={'yes' if token else 'no'} provider_key={'yes' if provider_key else 'no'}")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(endpoint, data=payload, headers=headers, method="POST"),
            timeout=60,
        ) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
    elapsed_ms = (time.perf_counter() - started) * 1000

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(f"[FAIL] HTTP {status}: non-JSON body: {body[:400]!r}")
        print("RESULT: FAIL")
        return 1

    if status == 200 and data.get("choices"):
        content = data["choices"][0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        returned_model = data.get("model", "?")
        print(f"[PASS] HTTP 200, model={returned_model}, {elapsed_ms:.0f} ms, usage={usage}")
        print(f"  planner reply: {content[:500]}")
        print("RESULT: PASS")
        print("RECORD IN README: LLM_BASE_URL format, PLANNER_MODEL value, auth headers used")
        return 0

    error = data.get("error", data)
    print(f"[FAIL] HTTP {status}, {elapsed_ms:.0f} ms: {json.dumps(error)[:500]}")
    if status == 401:
        print("  hint: gateway auth on? need cf-aig-authorization; provider key missing/stored?")
    elif status == 404:
        print("  hint: check URL format (custom-{slug}/... vs /compat) and slug prefix 'custom-'")
    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
