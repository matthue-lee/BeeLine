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
