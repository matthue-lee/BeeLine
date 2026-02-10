# Week 2 – Ingestion Pipeline Progress

## Highlights
- RSS client now respects per-feed cooldowns, exponential retry/backoff, robots.txt and exposes Prometheus metrics (`beeline_rss_requests_total`, `..._seconds`).
- HTML fetcher retries transient errors, detects Incapsula responses, and captures provenance (status, attempts, content length, headers).
- Cleaner removes Beehive-specific boilerplate, tracks removed sections, excerpts, and footer removal; provenance stores this alongside SHA-based dedupe IDs (URL + published timestamp).
- Repository logic preserves richer content, records provenance upgrades, and exposes new document filters in `/releases` (minister/portfolio/status/date).
- CLI now supports windowed backfills via `python -m beeline_ingestor backfill ...`; added `scripts/backfill_releases.py` wrapper for one-off historical imports.

## Validation Runs

### Synthetic Historical Import
To avoid hitting the production Incapsula wall during development, a 150-item synthetic feed was served over localhost and ingested:

```bash
BEEHIVE_FEEDS=http://localhost:8999/sample_feed.xml \
ENABLE_ENTITY_EXTRACTION=0 ENABLE_ARTICLE_FETCH=0 \
python -m beeline_ingestor --since 2024-01-01T00:00:00+00:00 --source synthetic
```

Output:

```
Run 5: total=150 inserted=150 updated=0 skipped=0 failed=0
```

SQLite now contains 160 releases (10 real + 150 synthetic) with status mix:

```
total 160
by_status {'OK': 10, 'PARTIAL': 150, 'FAILED_FETCH': 0, 'EMPTY_PARSE': 0}
```

### RSS Metrics
- `/metrics` exposes per-feed counters/histograms; use `python scripts/monitoring_smoke_test.py --metrics-url http://localhost:58000/metrics` to verify.
- When the Beehive site serves an anti-bot challenge, `beeline_rss_requests_total{status="robots"|"error"}` rises and the fetcher records `incapsula_detected`; remove the offending feed URL or pause ingestion rather than attempting to bypass protections.

## Backfill Instructions
1. Export or edit env vars (see `.env.docker`):
   ```bash
   export BEEHIVE_FEEDS="https://www.beehive.govt.nz/releases/feed?page=0,...,11"
   export ENABLE_ENTITY_EXTRACTION=0  # optional speed-up during backfill
   ```
2. Run rolling windows:
   ```bash
   python -m beeline_ingestor backfill \
     --start 2023-07-01T00:00:00+12:00 \
     --end 2024-06-30T23:59:59+12:00 \
     --window-days 14 --sleep-seconds 10
   ```
3. Or use helper script:
   ```bash
   ./scripts/backfill_releases.py --start 2023-01-01T00:00:00+12:00 --window-days 30
   ```
4. Inspect progress via `/releases?minister=Finance&status=OK&date_from=2024-01-01`.

## Next Steps
- Swap synthetic feed for production once Incapsula credentials/allow-listing are available.
- Automate monthly rolling backfill via GitHub Actions, reusing the new CLI windowing logic.
- Capture RSS/base metrics to Grafana dashboard and alert when error spikes exceed thresholds.
