# Runbook: Summarization Pipeline

## Overview
- **Components:** `SummaryService`, `LLMClient`, `prompt_templates` table, Redis summary cache, `CostTracker`/circuit breaker.
- **Inputs:** Cleaned release text from ingestion, active prompt template (`summarize`), metadata (title, categories, published date).
- **Outputs:** `summaries` row (short brief, why-it-matters, claims JSON, prompt version, tokens, cost, raw response) + cached payload in Redis for 24h.

## Common Operations
1. **List/manage templates**
   ```bash
   ./scripts/prompt_templates.py list --name summarize
   ./scripts/prompt_templates.py create summarize v1 --file prompts/summarize_v1.txt --author "ops" --description "Initial NZ policy tone" --temperature 0.2 --max-output-tokens 700
   ./scripts/prompt_templates.py activate summarize v1 --traffic 100
   ./scripts/prompt_templates.py show summarize v1
   ```
2. **Batch generation / QA**
   ```bash
   python scripts/generate_summaries.py --limit 100
   ```
   Observe `/releases` endpoint or DB entries for `summaries` rows with `prompt_version`.
3. **Manual override**
   Use `scripts/summary_override.py --release-id <id> --file override.md` (existing script) to patch summary text after human review.

## Failure Modes & Resolutions
| Symptom | Diagnosis | Action |
| --- | --- | --- |
| `CircuitOpenError` when summarizing | Hourly/daily/monthly spend exceeded | Check Grafana cost dashboard, lower concurrency or wait, optionally raise limits via env + redeploy. Circuit resets after `CB_COOLDOWN_SECONDS`. |
| `SummaryValidationError: LLM response was not valid JSON` | Model returned malformed payload | Inspect raw response in `summaries.raw_response`, adjust prompt or retry via `scripts/generate_summaries.py --limit 1 --release-id <id>`. Consider lowering temperature. |
| Summaries stale after release edit | Cache not invalidated | Run `redis-cli DEL summary:<release_id>` or rerun ingestion for affected release to trigger regeneration. |
| Cache miss causing DB surge | Redis unavailable | Set `SUMMARY_CACHE_REDIS_URL` or disable temporarily; pipeline falls back to DB reads but log warning. |

## Deployment Checklist
- Ensure `OPENAI_API_KEY` (or `LLM_MODE=mock` for offline) + `SUMMARY_MODEL` env vars set.
- `REDIS_URL` reachable for both circuit breaker and summary cache.
- At least one active template for `summarize`; `./scripts/prompt_templates.py list --active` should show entry.
- Run smoke test: `python scripts/generate_summaries.py --limit 5` and verify `summaries` rows contain cost/tokens.
- Update `docs/prompts/CHANGELOG.md` (if maintained) with new versions.

## Observability
- Metrics: `llm_calls_total` (via `/costs` endpoint) + Sentry breadcrumbs for guardrail failures.
- Logs: `SummaryService` emits warning on validation errors; `LLMClient` logs fallback to simulator when API unavailable.
- Dashboards: Grafana “LLM Spend” panel (hour/day/month) + “Summary Throughput” counter derived from `summaries` table.

## Escalation
- If multiple releases blocked, open incident, tag AI Lead + Ops.
- Provide prompt version, release IDs, and sample raw responses when filing GitHub issue for LLM regressions.
