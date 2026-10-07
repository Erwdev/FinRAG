# AGENTS.md — FinRAG

## Repo state (verify before acting)

- Scaffolding: almost every source file (`app/`, `flows/`, `dbt/`, `web/`, `eval/`, `pyproject.toml`, `Dockerfile`, `prefect.yaml`, `uv.lock`) is a **0-byte placeholder**. Real content today: `README.md`, `Architecture.md`, `infra/terraform/**`, `.gitignore`.
- **`Architecture.md` (Indonesian, v2.0.4) is the spec and source of truth.** Section map you will actually use:
  - §1 locked decisions + verified/unverified quotas · §3.3 deploy commands · §4 data/warehouse · §5 RAG (§5.2 SQL guard) · §6.2 prompt templates · **§6.4 four rails incl. full reference code** · §6.6 disclosures · §8 Redis keys/events · §9.2 route list + access matrix · §10 frontend patterns · §11.7 env vars · §12 file→purpose map · §13 build order, cut list, MVP acceptance · **§14 binding rules for implementers**
- Once code exists, executable code beats both docs; README/Architecture are English/Indonesian prose describing the same design.
- No CI, no pre-commit, no `opencode.json`, no test/lint config yet. Don't invent commands — when `pyproject.toml` is filled (§11) the intended dev tooling is `pytest`, `ruff`, `mypy` (§11.3).

## Non-negotiable (from Architecture.md §14)

- No trade execution / broker code; no new paid services; swap only to fallbacks already written in the doc (e.g. `TextSource` for X, CoinGecko for Binance).
- No sign-up or auto user creation: only rows in `app_user` (seeded manually) can log in; demo mode is client-only `DemoDataSource`, zero API calls.
- All LLM calls go through Cloudflare AI Gateway (`LLM_BASE_URL`) — never provider-direct from app code. Embeddings only via Pinecone Inference (`multilingual-e5-large`, 1024 dims).
- Disclosures are written server-side (`app/guardrails/disclosures.py`); the model never authors them. Scope rail runs before any terminal output → violation = `handoff`, never auto-repair.
- SQL guard (§5.2) must exist before the SQL tool is exposed to the LLM; free-tier guards (`PINECONE_MAX_VECTORS`, `EMBED_MONTHLY_TOKEN_CAP`, `FIRECRAWL_CREDIT_BUDGET`, `DAILY_LLM_BUDGET_USD`) before any flow is scheduled.
- Never cut: auth, the 4 rails, disclosures, citations, cost/quota caps (§13 cut list).

## Session rails (user-enforced)

- **Reuse, don't rebuild from zero.** Before writing any utility by hand, check (1) reference code pasted in `Architecture.md` (§6.2 prompts, §6.4 rails, §9.2 request/response bodies) — copy it, (2) the dependency list in §11 — prefer already-declared libs (`httpx`, `tenacity` retries, `sqlglot` for the SQL guard, `pydantic` schemas, `langchain` structured output, `upstash-redis`, `sqlalchemy`) over custom parsers/clients/retry loops, (3) stdlib before both. Only propose a new dependency if the spec has no answer, and route the choice through the user before adding it to `pyproject.toml`.
- **Ask before running bash.** Never execute a non-trivial script (install, deploy, migration, infra apply, anything mutating remote state or reading secrets) without first asking the user to confirm. Prefer proposing the exact command over running it silently.
- **Secrets: offer a script, don't improvise.** If a task needs secrets/keys (e.g. `.env.prod.yaml`, Prefect Secret block, GCP SA key), do not generate or echo them inline. Instead, suggest creating a reviewable generator script (e.g. `scripts/gen_secrets.sh` using `openssl rand -hex 32` / placeholders) and let the user run it. Never write generated secrets into tracked files, chat output, or logs; the `.gitignore` "never let an agent read these" list applies to you too.

## Commands (from README §Installation / Architecture §3.3)

```bash
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed_user --clerk-user-id user_XXXX --email you@example.com

cd infra/terraform && terraform init && terraform apply
gcloud run deploy finrag-api --source . --region us-east1 --env-vars-file .env.prod.yaml   # run from repo root; .env.prod.yaml is NOT committed

prefect cloud login
prefect work-pool create finrag-managed --type prefect:managed
prefect deploy --all

cd web && npm install && npm run dev          # local
cd web && vercel deploy --prod                # frontend prod
```

- Terraform: R2 state backend in `backend.tf` is **commented out** — fill it, then `terraform init -migrate-state`. `.terraform/` and `*.tfstate` are gitignored; `.terraform.lock.hcl` is committed. Provider: `hashicorp/google ~> 6.0`, TF `>= 1.9.0`.
- Eval: `eval/questions.jsonl` + `eval/run_eval.py` (§13.2) — used to calibrate `MIN_SIMILARITY` and measure rail hit/handoff rates. Script is still empty; check its CLI before running.

## Architecture facts that change how you code

- **One FastAPI service** (`app/main.py` = `app.main:app`): public routes + the "worker" internal route `POST /internal/jobs/{id}/run` (OIDC verified in-app, idempotent). Chat is **non-streaming**: `POST /chat` → 202 + job id, client polls `GET /jobs/{id}?after_seq=N`.
- **API stays import-light**: no pandas, no `google-cloud-storage` in the api deps (§11.1); `pandas`/`pyarrow` exist only in the `flows` extra — Cloud Run cold start matters (`--cpu-boost`, lazy imports).
- EMA cannot be done in BigQuery dbt (recursion) → pure-Python `app/indicators.py`, shared by chart routes and agent tools (§4.3).
- Rails are **pure functions** in `app/guardrails/rails.py` with fixed constants (`MIN_SIMILARITY=0.78`, half-life tweet 36h / news 120h, `MAX_QUESTION_CHARS=500`) — the full reference implementation is pasted in §6.4; copy it rather than redesigning.
- Retrieval flow: Pinecone top_k 30 → retrieval rail → dedupe `chunk_hash` → top 8 → chronological. Metadata pre-filter uses numeric `published_at_ts` epoch + `ticker` (§5.3).
- Fixed 10-coin universe in `config/universe.yaml`; portfolio holdings validated against it. `web/lib/disclosures.ts` must stay text-identical to `disclosures.py`.
- dbt: Inmon layers `finrag_raw` / `finrag_stg` / `finrag_mart`; BigQuery project needs **active billing** (sandbox blocks DML → dbt incremental breaks, §3.3).

## Conventions and gotchas

- New prose/docs in English; `Architecture.md` stays Indonesian. System prompts are English (§6.2) even though the spec's examples mix languages.
- Secrets: `.gitignore` explicitly marks `.env*`, keys, `*credentials*.json` as "never let an agent read these" — don't read or commit them. Prod env goes to Cloud Run `--env-vars-file`, Prefect Secret blocks, Vercel env.
- Idempotency is a hard requirement: deterministic landing paths, staging dedupe, job-status check on re-run (§14.12).
- Follow the §13 hour-block order and its cut list; apply cuts without waiting for approval (§14.13).
