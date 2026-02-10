# Week 4 Report

## Day 1 – Cost Tracking Foundations
- Added `CostTracker` module (`beeline_ingestor/costs.py`) to log every LLM/News API call into
  `llm_calls` + `daily_costs`, compute USD estimates via model pricing tables, and publish
  hourly/daily totals to Redis for future circuit breakers.
- Scripted `scripts/mock_cost_event.py` so developers can emit synthetic calls and verify the
  new `/costs` API plus DB rollups.
- Exposed `/costs` endpoint that summarizes spend/usage for the last N hours along with recent
  daily totals, enabling Grafana panels and ad-hoc checks.
- Documented workflow updates in `docs/monitoring.md` and built unit tests for the tracker.

Next: wire circuit-breaker logic + admin overrides (Day 2) and hook metrics into Grafana/alerts.

## Day 2 – Circuit Breakers & Admin Controls
- Added `CircuitBreaker` with Redis-backed sliding windows (hour/day/month) and integrated it into
  `CostTracker`. When spend crosses a limit, the breaker opens, emits an alert, and subsequent
  operations raise `CircuitOpenError` so callers can switch to fallbacks (extractive summaries,
  cached news links, etc.).
- Exposed CLI tooling (`scripts/circuit_breaker_admin.py`) to inspect/reset/manual-open breakers,
  plus `ENABLE_COST_BREAKER`/`CIRCUIT_BREAKER_*` env vars for tuning.
- Added unit tests for the breaker and updated documentation to describe the workflow + fallback
  expectations.

Next: Day 3 wiring (Grafana dashboards + alert routing), evaluation datasets, runbooks.

## Day 3 – Monitoring & Alerting
- Added Prometheus/Grafana assets under `monitoring/` (scrape config, dashboard JSON, alert rules)
  covering queue depth, job throughput, and cost trends. Documented how to wire alerts to Slack or
  email and how to consume breaker events via Redis.

## Day 4 – Evaluation Datasets
- Created labeled datasets (`evaluation/datasets/summary_gold.jsonl`, `evaluation/datasets/ir_labels.jsonl`)
  with 50 releases each for summarization and IR evaluation, plus README instructions for loading
  them into nightly jobs/storage.

## Day 5 – Runbooks & Chaos Drills
- Authored incident runbooks in `runbooks/` covering cost overruns, LLM outages, queue backlogs, and
  digest failures, providing checklists and remediation steps.
- Validated breaker CLI + replay tooling to ensure operators can exercise fallbacks and resets.
