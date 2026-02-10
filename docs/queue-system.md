# Queue & Worker System (Week 3)

## Overview
- **Queues (BullMQ):** `ingest`, `summarize`, `verify`, `embed`, `link`, `entity_extract`.
- **Workers:** Node/TypeScript processes using BullMQ + Redis. Each worker exposes Prometheus metrics (Week 4) and logs via `pino`.
- **Persistence:** Every job records a row in `job_runs`; terminal failures are mirrored in `failed_jobs` for replay.

## Configuration
Environment variables for workers (see `workers/src/config.ts`):

| Variable | Default | Description |
| --- | --- | --- |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `REDIS_QUEUE_PREFIX` | `beeline` | Key prefix per environment |
| `DATABASE_URL` | `postgresql://beeline:beeline@localhost:5432/beeline` | Postgres connection for job bookkeeping |
| `WORKER_QUEUE` | `ingest` | Queue to process |
| `WORKER_CONCURRENCY` | `5` | Parallel jobs per worker |
| `WORKER_MAX_ATTEMPTS` | `3` | Retry attempts before DLQ |
| `WORKER_BACKOFF_INITIAL_MS` | `1000` | Initial exponential backoff |

## Retry Policy (per queue)
- `ingest`: attempts=3, exponential backoff (1s base), DLQ recorded after final failure.
- `summarize`: attempts=5 (set via job options when enqueued), to tolerate transient LLM/API glitches.
- `verify`, `embed`, `link`, `entity_extract`: default attempts=3 until the respective workers are implemented (Week 4/5).

## Dead-letter Handling
1. When a job exhausts retries, `JobStore.recordRunFailure` inserts into `failed_jobs` with payload + error.
2. Ops replay via:
   ```bash
   cd workers
   npm run replay-failed -- 20   # requeue up to 20 failed jobs
   ```
   Each record is removed from `failed_jobs` after successful enqueue.
3. Runbooks should document how to inspect `failed_jobs` in Postgres before replaying suspicious payloads.

## Local Development
```bash
cd workers
npm install
npm run dev        # start ingest worker (uses ts-node)
npm run enqueue-demo -- 50   # fire 50 synthetic jobs
npm run replay-failed -- 10  # requeue DLQ items after fixes
# Load test example
npm run enqueue-demo -- 200
```

The Flask API now exposes `/jobs?status=failed&limit=20` for quick inspection, and `/releases` includes downstream data for verifying queue results once real workers ship.

Further integration (Week 4+) will connect ingestion events to queue producers and attach metrics/health endpoints to each worker container.

## Runbook (Week 5)
1. **Check worker health:** `curl http://localhost:9100/health`.
2. **Monitor metrics:** `curl http://localhost:9100/metrics` for `queue_job_results_total` and `queue_depth_total`.
3. **Inspect jobs:** `GET /jobs?status=failed` via the ingestion API or query `failed_jobs` in Postgres.
4. **Replay DLQ:** `cd workers && npm run replay-failed -- 20` after verifying payloads.
