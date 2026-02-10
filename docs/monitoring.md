# Monitoring Foundations

This service now exposes baseline instrumentation required for the Week 1 Day 3
deliverable: Prometheus-style metrics for pipeline health and Sentry wiring for
error reporting.

## Sentry Configuration

Set the following environment variables (already referenced in
`docker-compose.yml`):

- `SENTRY_DSN` – Project DSN from the Sentry dashboard.
- `SENTRY_ENVIRONMENT` – Defaults to `development` if unspecified.
- `SENTRY_TRACES_SAMPLE_RATE` – Optional float (`0.0` by default).
- `SENTRY_PROFILES_SAMPLE_RATE` – Optional float (`0.0` by default).

Both the Flask API and the CLI/worker initialise Sentry automatically when a
DSN is present. To validate the wiring without causing noisy exceptions, run:

```bash
python scripts/monitoring_smoke_test.py --emit-sentry-event
```

The script emits a synthetic marker so the project dashboard shows at least one
captured event, satisfying the playbook requirement.

## Prometheus Metrics

`/metrics` is available on the ingestion API and serves Prometheus text
formatting. Core gauges/counters include:

- `beeline_ingestion_runs_total{status="..."}` – run counts per outcome.
- `beeline_ingested_documents_total{result="..."}` – document tallies by
  result (inserted/updated/skipped/failed).
- `beeline_ingestion_run_seconds` – histogram of run durations.
- `beeline_releases_total` – gauge of documents stored.
- `beeline_ingestion_last_success_unixtime` – timestamp of the last successful
  run.

Verify the endpoint locally:

```bash
python scripts/monitoring_smoke_test.py --metrics-url http://localhost:58000/metrics
```

The script checks for key metric names so CI or local smoke tests can fail fast
if instrumentation regresses.

### RSS Fetch Metrics

Week 2 adds counters and histograms for the RSS client so you can monitor
upstream stability:

- `beeline_rss_requests_total{feed="…", status="200"}` – increments per
  request grouped by HTTP status (`robots`/`error` when no HTTP code exists).
- `beeline_rss_request_seconds{feed="…"}` – latency histogram for each feed.

The metrics are emitted automatically by `FeedClient` and appear on
`/metrics`. Use them to detect throttling (spikes in 429) or slow feeds.

### Cost Tracking

- Use `scripts/mock_cost_event.py` to emit a synthetic LLM call and verify
  `llm_calls`/`daily_costs` entries plus the `/costs` API:

```bash
./scripts/mock_cost_event.py --model gpt-4o-mini --operation summarize
curl http://localhost:58000/costs?hours=24
```

- Redis (if configured) tracks hourly/daily spend under keys like
  `cost:hour:summarize:YYYYMMDDHH`; these drive the circuit-breaker logic slated
  for Day 2.

### Dashboards & Alerts
- See `monitoring/` for sample Prometheus scrape configs, Grafana dashboard JSON, and alert rules
  (queue backlog, job failure rate). Import the dashboard and configure Alertmanager routes for
  Slack/email as described.
