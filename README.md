# FinRAG

![Status](https://img.shields.io/badge/status-48--hour%20build-orange)
![Plan](https://img.shields.io/badge/docs-Architecture%20v2.0.4-informational)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Dependencies](https://img.shields.io/badge/dependencies-uv.lock-green)

**Technology**:
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-7B42BC?logo=terraform&logoColor=white)
![Pinecone](https://img.shields.io/badge/Pinecone-242627)
![Neon](https://img.shields.io/badge/Neon-00E599)
![Sentry](https://img.shields.io/badge/Sentry-362D59?logo=sentry&logoColor=white)
![Langfuse](https://img.shields.io/badge/Langfuse-17B8A6)
![Clerk](https://img.shields.io/badge/Clerk-6C47FF)
![Cloudflare](https://img.shields.io/badge/Cloudflare-F38020?logo=cloudflare&logoColor=white)

## Executive Summary

FinRAG is a private crypto portfolio copilot. It combines daily price time series, RSS news, and post data from X, then answers free-form chat questions with a structured, cited assessment. It is a decision-support tool only: no trade execution, no personalized financial advice, no promised outcomes.

The system has two engineering sides working together:

- **Data engineering**: scheduled ingestion from market and text sources into an Inmon-style BigQuery datawarehouse (raw, staging, marts), dbt transformations with tests, and chunk embeddings into Pinecone.
- **AI engineering**: a deterministic RAG pipeline (planner, parallel retrieval, temporal re-rank, context builder, final LLM with structured output) wrapped by four guardrail rails, routed through Cloudflare AI Gateway, and observed with Langfuse and Sentry.

One backend service (`finrag-api` on Cloud Run) serves both the public API and the internal job runner; Cloud Tasks triggers long-running chat jobs. The frontend is a single-page Next.js terminal-style dashboard with a client-only demo mode.

Full design and 48-hour build plan: [`Architecture.md`](Architecture.md).

## Project Structure

```
FinRAG/
  app/                 # FastAPI service: routes, auth, agent pipeline, guardrails
  flows/               # Prefect flows: ingest prices, ingest news, scrape X, build and embed
  dbt/                 # BigQuery transformations: staging views, mart tables, tests
  config/              # Asset universe (fixed 10 coins)
  scripts/             # Manual seeding (owner user)
  web/                 # Next.js dashboard (App Router), empty scaffolding
  eval/                # Retrieval and guardrail evaluation sets
  infra/terraform/     # IaC: worker, iam, bigquery, storage, tasks; state on Cloudflare R2
  Architecture.md      # Design document (source of truth)
```

## High-Level Architecture

```mermaid
flowchart LR
  subgraph CR["Online lane: Cloud Run (GCP) - one FastAPI service, scale-out per request"]
    API["finrag-api (FastAPI)<br/>public routes: chat, charts, feed, portfolio"]
    JOB["Internal job route - the 'worker'<br/>/internal/jobs/{id}/run<br/>RAG pipeline in one long request"]
  end

  subgraph PF["Batch lane: Prefect Cloud - orchestration and control plane"]
    CTRL["Control plane<br/>schedules, retries, state, logs"]
    RUN["Execution plane: ephemeral Python runners<br/>(one per flow run, no cluster to own)<br/>ingest -> land -> load -> dbt -> chunk -> embed"]
    CTRL --> RUN
  end

  subgraph ST["Storage and compute"]
    PG[("Neon Postgres")]
    RD[("Upstash Redis")]
    BQ[("BigQuery datawarehouse<br/>distributed SQL: the MPP engine")]
    PC[("Pinecone vectors")]
  end

  WEB["Next.js dashboard<br/>(Vercel)"]
  TASKS["Cloud Tasks<br/>queue and retries"]
  SRC["Market, RSS, X sources"]
  CFGW["Cloudflare AI Gateway"]
  LLM["LLM providers"]
  LF["Langfuse<br/>LLM traces"]
  SE["Sentry<br/>errors"]

  WEB -->|"JWT (Clerk)"| API
  WEB -.->|"live prices: WebSocket,<br/>browser direct"| SRC
  API -->|"enqueue chat job"| TASKS
  TASKS -->|"OIDC, internal route"| JOB
  API --> PG
  API --> RD
  API -->|"charts, feed"| BQ
  JOB --> PG
  JOB --> RD
  JOB -->|"indicators"| BQ
  JOB -->|"top_k search"| PC
  JOB --> CFGW
  RUN --> SRC
  RUN -->|"load jobs"| BQ
  RUN -->|"upsert vectors"| PC
  JOB -.->|"traces"| LF
  JOB -.->|"errors"| SE
  API -.->|"errors"| SE
```

The three boxes are deliberately separate compute domains: **Cloud Run** is stateless HTTP scale-out (N replicas, one independent request each), **Prefect** is orchestration only (its managed pool creates a fresh runner per flow run — Kubernetes-Job semantics without owning a cluster), and **BigQuery** is the actual distributed/MPP compute for all warehouse SQL.

Component summary:

| Layer | Components | Role |
| --- | --- | --- |
| Frontend | Next.js on Vercel | Terminal dashboard, demo mode, chat thread |
| Auth | Clerk | Third-party sign-in for the single owner account |
| Compute (online) | Cloud Run (`finrag-api`), Cloud Tasks | One FastAPI service: public routes + internal job route ("the worker"); chat jobs are single long requests with retries via Cloud Tasks |
| Data warehouse | BigQuery datawarehouse | Inmon-style layers over open-format landing files; dbt models and tests; the only distributed (MPP) compute in the stack |
| State | Neon Postgres, Upstash Redis | 4-table app data; job status, events, rate limits, budget counters |
| Vectors | Pinecone | `multilingual-e5-large` index (1024 dims), embeddings and search |
| Orchestration (batch) | Prefect Cloud | Control plane (schedules, retries, state) plus managed work pool executing ephemeral Python runners for the four flows (prices, news, X, build and embed) |
| AI | Cloudflare AI Gateway, OpenCode Go, fallback providers | Single LLM egress with routing, fallback, rate limits |
| Observability | Langfuse, Sentry | Per-stage LLM traces; application errors and alerting |
| Infra | Terraform, Cloudflare R2 | IaC modules; remote state on R2 |

### Execution Model: Batch and Online

The system runs in two tempos. Both are serverless; neither requires a dedicated ingestion or worker service — Prefect's managed pool and Cloud Run scale to zero.

| Tempo | Runner | Work |
| --- | --- | --- |
| Batch (scheduled) | Prefect Cloud managed pool | ingest -> landing -> BigQuery load -> dbt build -> **chunking** -> **embedding** -> Pinecone upsert. Four flows: prices/news every 6h, build+embed 4x/day, X capped at 12 runs/day |
| Online (per question) | Cloud Run route via Cloud Tasks | plan -> hybrid retrieval -> rail filter -> **temporal re-rank** -> context builder -> final LLM -> rails |

Re-rank is a deterministic score fusion at query time (no learned cross-encoder, no extra model calls):

```
score_final = cosine_similarity x 0.5^(age_hours / half_life) x source_weight
```

- Half-life: tweets 36h, news 120h. Source weight: tweets 0.7, news 1.0.
- Flow: Pinecone top_k 30 -> retrieval rail -> de-dupe by `chunk_hash` -> top 8 -> chronological order.

Metadata filtering happens at two gates:

- **Pre-filter in Pinecone**: `ticker in [...]` and `published_at_ts >= now - window`. The `published_at_ts` epoch field is stored numeric specifically for filtering; the window comes from the planner (1-90 days).
- **Post-filter in the retrieval rail**: minimum similarity 0.78 (e5 scores cluster tightly), per-source maximum age, ticker consistency with the plan, injection-pattern scan, at least 2 evidence items per ticker.

**Non-streaming by design**: `POST /chat` returns 202 with a job id, then the client polls `GET /jobs/{id}?after_seq=N` every 2 seconds for ordered progress events and the final JSON result. No SSE or token streaming — the frontend stays a simple poll-and-render loop.

### Scaling and Compute Rationale

Every compute choice below is a documented tradeoff, not a framework default. Four mechanisms, four different jobs:

| Mechanism | Role | Explicitly not |
| --- | --- | --- |
| Prefect control plane | Decides what runs when: schedules, retries, state, backfills | Not a worker fleet — it only orchestrates |
| Prefect managed runners | Execution plane: a fresh isolated Python runner per flow run (Kubernetes-Job semantics, zero cluster operations) | Not MPP — each run is a single process |
| BigQuery | The MPP engine: dbt and warehouse SQL execute distributed across BigQuery slots | Not a system you feed Spark to |
| Cloud Run | Stateless HTTP scale-out: N replicas, each handling one independent request | Not parallelism over a single dataset |

- **Batch ELT, not streaming**: raw data is landed first (Parquet/JSON in GCS), loaded into `raw_*`, then transformed inside the warehouse by dbt. Discrete cron batches and BigQuery load jobs; no Kafka/Flink — stream processing buys nothing at ~300 chunks/day. Idempotent reruns make batches safe.
- **Python only, no PySpark/JVM**: volumes are KB-MB per day. A Spark runtime would add hundreds of MB and seconds of startup to every run for zero throughput gain, while BigQuery already provides the distributed compute. Flows use `pandas` + `pyarrow` for Parquet only; the online path is pandas-free pure Python to keep Cloud Run imports fast.
- **The only streaming is display-only**: the browser connects to Binance's public WebSocket directly for live prices; it never enters the data pipeline.

## Concepts Explored

**Data engineering**

- **Inmon datawarehouse pattern**: raw, staging, and mart layers in BigQuery instead of a star schema; downstream models read open-format (Parquet/JSON) landing data without multi-table joins on ingest.
- **Batch ELT**: land raw files first, load, transform in-warehouse with dbt — discrete idempotent batches instead of streaming, with no message broker in the path.
- **Orchestration**: Prefect Cloud flows with schedules, locks, and token buckets; no custom worker nodes.
- **Control plane / execution plane split**: Prefect Cloud orchestrates; a fresh ephemeral runner executes each flow run (Kubernetes-Job semantics, zero cluster ops); BigQuery does the distributed compute. See "Scaling and Compute Rationale".
- **Chunking RAG**: text split at 800 chars with 100 overlap, ticker fan-out, capped under embedding input limits.
- **Database abstraction**: warehouse access through parameterized tools and guarded read-only SQL, never free-form joins from the model.
- **Idempotency**: deterministic landing paths, staging de-duplication, job status checks on re-run.
- **Free-tier engineering**: quota guards for vectors, embedding tokens, crawl credits, and LLM budget.

**AI engineering**

- **Hybrid retrieval**: vector search (Pinecone) combined with structured retrieval (indicators, portfolio, last prices) planned per question.
- **Temporal re-rank**: similarity decayed by source half-life (tweet 36h, news 120h), then de-duplicated and time-ordered.
- **Context builder**: indicators serialized as YAML, evidence as annotated XML blocks with ids for citation.
- **Structured output**: Pydantic-constrained plan and recommendation schemas with one repair attempt.
- **Guardrails**: four deterministic rails (input, retrieval, output, scope) plus server-written AI and financial-responsibility disclosures; scope violations route to human handoff.
- **Prompt engineering**: English system prompts, untrusted-evidence rules, no-advice scope rules.
- **LLM gateway routing**: one egress through Cloudflare AI Gateway with provider fallback configured outside the code.
- **Observability**: Langfuse for per-stage LLM traces, Sentry for exceptions on the single service.

**Platform and operations**

- **IaC (Terraform)**: worker, IAM, BigQuery, storage, and tasks as code; state on Cloudflare R2.
- **Scale-out vs MPP**: Cloud Run scales replicas per HTTP request, BigQuery scales slots per query — two different scaling axes chosen deliberately; no Spark/JVM anywhere at this data volume.
- **Third-party auth (Clerk)**: sign-in only, no sign-up; user mapping in `app_user`, API rejects unknown subjects.
- **Event-driven jobs**: Cloud Tasks invokes an idempotent internal route; progress exposed as ordered Redis events.

## Installation

Prerequisites: `uv`, `gcloud`, `terraform`, `prefect`, `dbt`, Node 22+, `vercel`.

```bash
# 1. Infrastructure (state backend on Cloudflare R2 configured later)
cd infra/terraform && terraform init && terraform apply

# 2. Backend
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed_user --clerk-user-id user_XXXX --email you@example.com

# 3. Data flows
prefect cloud login
prefect work-pool create finrag-managed --type prefect:managed
prefect deploy --all

# 4. Frontend (scaffolding only; contents filled during the frontend build block)
cd web && npm install && npm run dev
```

Deploys: `gcloud run deploy finrag-api --source .` and `cd web && vercel deploy --prod`. Environment variables are listed in `Architecture.md` section 11.7; copy `web/.env.local.example` for local values.

## Usage and Examples

- Open `/`: empty dashboard with **Use Demo Mode** (client-only fixtures, no API calls) or **Sign in** for the owner.
- Chat: `POST /chat` returns 202 and a job id; the dashboard polls for progress events and renders the cited assessment when the job reaches a terminal status.
- **Get Today's Recommendation**: one click produces a daily brief, cached per UTC day and holdings hash.
- Guardrail checks (also available as demo prompts): "Buy 1 BTC now for me" (blocked), "Guarantee BTC returns next month" (handoff), "Ignore previous instructions" (blocked).
- Live prices arrive via public Binance WebSocket from the browser, with polling fallback.

## Status

Design document at `Architecture.md` v2.0.4. Repository scaffolding matches the plan; application and frontend files are empty placeholders pending the 48-hour build blocks.
