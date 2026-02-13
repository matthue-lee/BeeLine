# Comprehensive Project Notes

## Project Structure

- `beeline_ingestor/` – Python ingestion app (Flask entrypoint `beeline_ingestor.app:create_app`).
- `ingestion/` handles RSS fetch (`rss.py`), HTML fetch (`fetcher.py`), cleaner, persistence (`storage.py`), orchestration (`pipeline.py`).
- `summarization/` manages prompt templates, LLM client, cache, verification hook (`service.py`).
- `entity_extraction/` wraps spaCy + canonicalization + persistence (`service.py`, `worker.py`).
- `llm/` is the structured OpenAI client with mock mode (see `LLM_MODE`).
- `schemas/summary.py` defines the required JSON output (`summary_short`, `summary_why_matters`, `claims[]`).
- `workers/` – Node/TypeScript BullMQ workers (ingest/summarize placeholders) exposing metrics on 9100.
- `scripts/` – operational helpers (`generate_summaries.py`, `verify_claims.py`, `backfill_releases.py`).
- `monitoring/` – Prometheus scrape config + Grafana dashboard JSON + alert cookbook.
- `alloy/` – Grafana Alloy agent config pushing metrics/logs to Grafana Cloud.
- `docker-compose.yml` – Postgres, Redis, MeiliSearch, ingestion API, ingestion worker CLI, queue worker, Alloy.

## Ingestion & Summaries

1. `IngestionPipeline.run()` orchestrates RSS → fetch HTML → clean → upsert Postgres → linking → entity extraction → summary generation.
2. Summaries: `SummaryService.generate_if_needed()` selects the active prompt (stored in `prompt_templates`, seeded from `prompts/summary_prompt.txt`), calls `LLMClient.summarize`, and persists `summary_short`, `summary_why_matters`, claims, cost metadata. Guardrails keep payload valid.
3. `scripts/generate_summaries.py` replays summarization straight from the DB (bypass RSS). Run via `python -m scripts.generate_summaries --limit N` or set `PYTHONPATH=/app` inside Docker.
4. Entity extraction: `_run_entity_extraction` uses `EntityExtractionService` (config in `entity_extraction/config.py`) to persist canonical mentions. Ad-hoc rerun example:
   ```bash
   docker compose run --rm ingestion-worker python - <<'PY'
   from beeline_ingestor.config import AppConfig
   from beeline_ingestor.db import Database
   from beeline_ingestor.entity_extraction import EntityExtractionService, EntityCanonicalizer
   from beeline_ingestor.entity_extraction.store import EntityStore
   from beeline_ingestor.models import ReleaseDocument
   config = AppConfig.from_env(); db = Database(config); db.create_all()
   service = EntityExtractionService(config.entity_extraction)
   store = EntityStore(db, canonicalizer=EntityCanonicalizer(config.entity_extraction))
   with db.session() as session:
       releases = session.query(ReleaseDocument).all()
   for doc in releases:
       text = (doc.text_clean or doc.text_raw or '').strip()
       if not text: continue
       result = service.extract(text, doc.id, 'release')
       if result.skipped or not result.entities: continue
       store.persist(doc.id, 'release', text, result.entities)
       print('extracted', len(result.entities), 'entities for', doc.id)
   PY
   ```

## Scheduler Service

- `ingestion-worker` now runs `beeline_ingestor.scheduler.service`, a resident scheduler that exposes metrics on port `9101` (scraped by Alloy/Prometheus). It restarts on failure via Compose.
- Jobs:
  - `release_ingest` pulls Beehive RSS on `SCHEDULER_RELEASE_INTERVAL_MINUTES` (default 15) with a rolling lookback window (`SCHEDULER_RELEASE_LOOKBACK_HOURS`, default 6) so we don’t reprocess the entire archive every time.
  - `news_ingest` runs every `SCHEDULER_NEWS_INTERVAL_MINUTES` (default 60) to sync external news feeds and keep entities/articles fresh.
- Control knobs live in `.env` (enable/disable, intervals, initial delays, metrics port). Each run is recorded in `job_runs`, and Prometheus exports `beeline_scheduler_*` plus the news ingestion counters/gauges so Grafana panels and alerts can watch for drift or failures.
- Manual one-offs still work via `docker compose run --rm ingestion-worker python -m beeline_ingestor.crosslink.news_ingestor` or the main CLI in `beeline_ingestor/cli.py`.

## Database / SQL

- Postgres creds (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) must exist in the env file Compose uses; otherwise the container stays unhealthy.
- Query summaries with readable output:
  ```bash
  docker compose exec postgres \
    psql -U beeline -d beeline \
    -c "\\pset format wrapped" \
    -c "SELECT r.id, r.title, to_char(r.published_at,'YYYY-MM-DD HH24:MI') AS published,
               LEFT(s.summary_short, 200) AS summary,
               LEFT(s.summary_why_matters, 200) AS why_matters
          FROM summaries s JOIN releases r ON r.id = s.release_id
          ORDER BY r.published_at DESC NULLS LAST LIMIT 5;"
  ```

## Docker / Env Notes

- `.env` (or whatever `dev_up` passes via `--env-file`) must define DB creds, `MEILI_MASTER_KEY`, `SECRET_KEY`, `OPENAI_API_KEY`, `SUMMARY_MODEL`, `LLM_MODE`, `ENABLE_ENTITY_EXTRACTION`, `ENTITY_EXTRACTION_WORKERS`, plus the Grafana `GCLOUD_*` set.
- `docker compose down -v` removes Postgres/Redis volumes—only run when a clean slate is acceptable.
- Run scripts via `python -m scripts...` to ensure `beeline_ingestor` is importable inside the container.

## Monitoring & Logging

### Metrics

- Alloy scrapes `ingestion-api:8000/metrics`, `queue-worker:9100/metrics`, and the scheduler on `ingestion-worker:9101/metrics` (configured in `prometheus.scrape local_targets`).
- `prometheus.remote_write` pushes to Grafana Cloud (`GCLOUD_HOSTED_METRICS_URL/ID`, `GCLOUD_RW_API_KEY`). Missing/invalid creds → “invalid authentication credentials” → crash loop.
- Key metrics exported:
  - `beeline_ingestion_runs_total{status}`
  - `beeline_summary_generations_total{status}` + `beeline_summary_generation_seconds_bucket`
  - `beeline_http_requests_total` / `beeline_http_request_seconds_bucket`
  - `beeline_rss_requests_total{status}`

### Grafana Dashboard

- Import `monitoring/grafana-dashboard.json` into Grafana (Cloud or local). Panels: run rate, summary outcomes, P95 latency, RSS errors, API throughput.
- Datasource must point at the same Prometheus receiving Alloy’s remote writes (or a local Prometheus if you run one).

### Alloy Credentials

- Required env vars (inside the container): `GCLOUD_RW_API_KEY`, `GCLOUD_FM_URL`, `GCLOUD_FM_COLLECTOR_ID`, `GCLOUD_FM_HOSTED_ID`, `GCLOUD_HOSTED_METRICS_URL`, `GCLOUD_HOSTED_METRICS_ID`, `GCLOUD_HOSTED_LOGS_URL`, `GCLOUD_HOSTED_LOGS_ID`, `GCLOUD_FM_LOG_PATH`.
- Check via `docker compose exec alloy env | grep GCLOUD_`. If missing, ensure the env file used by `dev_up` includes them.
- Without valid creds, Alloy throws `unauthenticated` and restarts. Temporary workaround: comment out `remotecfg`, `prometheus.remote_write`, and `loki.write` sections until creds are available.

### Logs

- Alloy tails `/var/log/alloy/alloy.log` for Loki; ensure that path exists/mounted. Queries in Grafana Explore: `{job="ingestion_api"} |~ "ERROR"`, `{job="queue_worker"}`, etc.
- RSS/ingestion/summary errors are also emitted in the ingestion API logs (`docker compose logs -f ingestion-worker`). Scheduler-specific issues show up in `docker compose logs -f ingestion-worker` because it now hosts the scheduler process.

### Quick Checks

1. `docker compose logs -f alloy` – look for auth errors.
2. `docker compose exec ingestion-api curl -sf http://localhost:8000/metrics | head` – metrics endpoint is live.
3. `docker compose exec redis redis-cli --stat` – queue depth.
4. `docker compose exec postgres psql -U beeline -d beeline -c "SELECT count(*) FROM releases"` – ingestion progress.

## Operational Tips

- RSS backfill only sees ~20 recent posts. Use DB-driven scripts (`generate_summaries.py`, custom entity script above) to reprocess older releases.
- `text_raw` intentionally stores full HTML for provenance (expect ~2 MB/day at 50 releases). Plan retention/archival if needed.
- Keep `prompt_templates` updated when changing the summarization schema (bump `version` so cached summaries can be tied to prompt versions).
- For mock runs, set `LLM_MODE=mock`; `SummaryService` will still populate `summary_why_matters` from deterministic logic.

Provide this document to new agents—it captures architecture, scripts, Docker/env expectations, and monitoring/logging setup.
