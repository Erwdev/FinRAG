
## Foundation Test Log (Hour 0-2)

Records the results required by `Architecture.md` §13 (jam 0 sampai 2), §13.1 (NF-5), and §14.4. Helper scripts live in `scripts/foundation_tests/`; run the AWS/MotherDuck/Prefect tests with the commands shown in `Architecture.md` §3.3.

**Cloudflare AI Gateway — custom provider URL format** (per official Cloudflare docs, checked 2026-10-08; confirm with a live call before relying on it):

| Item | Value |
| --- | --- |
| Provider-specific endpoint | `https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/custom-{slug}/{provider-path}` |
| Unified API (OpenAI-compatible) | `https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/compat/chat/completions` |
| Model field (unified API) | `custom-{slug}/{model-name}` |
| Model field (provider-specific) | `{model-name}` (path carries the provider) |
| Gateway auth header | `cf-aig-authorization: Bearer {CF_AIG_TOKEN}` |
| Provider key header | `Authorization: Bearer {LLM_API_KEY}` — omit if the key is stored in Cloudflare (`headers` field on the custom provider accepts credentials) |
| Known pitfall | Gateway may prepend `/v1` to upstream paths (cloudflare/ai#476): set custom-provider `base_url` to the provider root and put `/v1/chat/completions` in the request path, or vice versa — verify during the first live test |

### Mandatory hour 0-2 verification (Architecture.md §F)

| # | Test | Expected result | If it fails | Result |
| --- | --- | --- | --- | --- |
| 1 | MotherDuck account region | us-east-1 | Recreate the account before any data exists | |
| 2 | MotherDuck reads private `s3://` through a persistent secret | `SELECT count(*) FROM read_parquet('s3://...')` succeeds | Fallback §4.2 | |
| 3 | dlt writes Parquet to S3 from Prefect Serverless | Files appear, layout and state are restored on the second run | Adjust the load paths in §4.2, or dlt straight to the MotherDuck destination | |
| 4 | `pip_packages` and `git_clone` on Prefect Serverless | `dlt`, `dbt-duckdb`, `pinecone` installed, code pulled | Shrink dependencies, split the flow | |
| 5 | Minutes for one hello flow run | Matches the §4.5 assumption | Update the budget table and levers | |
| 6 | Locked `duckdb` version connects to `md:` from Lambda with the pre-installed extension | Connection and query succeed with no download at cold start | Align `duckdb` with the version MotherDuck supports | |
| 7 | The RO token cannot write | `CREATE TABLE` rejected | Use a read scaling token, or separate access via a role | |
| 8 | `enable_external_access=false` on the `md:` connection | Active without breaking queries | Rely on the allowlist and the RO token | |
| 9 | Function URL reachable from a browser | `GET /health` returns 200 | Check `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` permissions | |
| 10 | SQS triggers the worker | Test message processed, DLQ empty | Check the worker role permissions and visibility timeout | |
| 11 | Binance from Prefect Serverless and Lambda | Data received, not 451 | Try `data-api.binance.vision`, then the CoinGecko fallback | |
| 12 | dbt build from Prefect Serverless | Finishes inside the minute budget | Split the number of models per run | |
| 13 | Lambda, SQS, egress, account concurrency, and Prefect quotas | Match the §1.2 assumptions | Update §1.2 and the §4.5 levers | |
| 14 | Cost Explorer after 24 hours | NF-5 satisfied | Find the egress source or stray NAT, fix before hour 34 | |

### Additional hour 0-2 checks (§13 row 0-2)

| # | Test | Command | Date | Result | Notes |
| --- | --- | --- | --- | --- | --- |
| 15 | Hello URL on Lambda | `curl $FUNCTION_URL/health` | | | image built with `--provenance=false`, function deployed by Terraform |
| 16 | Planner call via gateway (local) | `python scripts/foundation_tests/test_gateway_planner.py` | | | record `LLM_BASE_URL` format + model name in this README |
| 17 | Planner call via gateway (from Lambda) | same script invoked from the function | | | |
| 18 | Binance klines (local) | `python scripts/foundation_tests/test_binance.py` | | | watch 451/403 |
| 19 | Binance klines (Prefect Serverless) | same script from a Prefect flow run | | | |
| 20 | Firecrawl X search | `python scripts/foundation_tests/test_firecrawl_x.py` | | | record credits used per scrape |
| 21 | News RSS | `python scripts/foundation_tests/test_rss.py` | | | record feed URL chosen as `NEWS_RSS_URL` |

### Quota verification (§1.1 unverified list)

| Item to verify | Free-tier value | Verified? | Date / source |
| --- | --- | --- | --- |
| MotherDuck free plan (10 GB, 10 Pulse-hours, region lock, read-only tokens, `enable_external_access`) | ? | | |
| Prefect Hobby (500 Serverless min/month, 5 deployments) | ? | | |
| AWS free tier: Lambda requests/GB-seconds, SQS, CloudWatch, ECR, SSM, monthly egress | ? | | |
| AWS new-account Lambda concurrency quota; `reserved_concurrent_executions` allowed? | ? | | |
| dlt filesystem layout, state restore, correct pip extra names | ? | | |
| Prefect Serverless: `pip_packages`, `git_clone`, work pool type, private repo pull | ? | | |
| Clerk: sign-up disable possible on free plan? | ? | | |
| Firecrawl credit cost for an X page | ? | | |
| Binance accepts Prefect Serverless / Lambda IPs (no 451) | ? | | |
| News RSS access | ? | | |
| Gateway URL format + model name for OpenCode Go | see table above | | |
| Provider key storable in Cloudflare for custom provider | docs say yes (`headers`) | | |
| AI Gateway free-tier log quota + rate limits | ? | | |
| Fallback rule syntax to OpenRouter in gateway | ? | | |
| Langfuse Hobby quota and retention | ? | | |

Deploys: build and push the image (`docker buildx build --platform linux/amd64 --provenance=false ... --push`), then `terraform apply -var image_tag=$GIT_SHA` for the two Lambdas; `cd web && vercel deploy --prod` for the frontend. Lambda secrets live in SSM Parameter Store and flow secrets in Prefect Secret blocks (never in env files or Terraform state). Environment variables are listed in `Architecture.md` section 11.7; copy `web/.env.local.example` for local values. `NEXT_PUBLIC_API_URL` must contain the Lambda Function URL (or a custom domain in front of it).