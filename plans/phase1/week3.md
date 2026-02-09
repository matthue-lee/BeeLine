# Week 3: Job Queue System – Execution Playbook

## Mission & Success Criteria
- Introduce BullMQ/Redis-backed queues that decouple ingestion from downstream processing (summaries, verification, entity extraction, cross-linking).
- Provide worker framework with shared logging, retries, DLQ handling, and metrics.
- Persist job state in Postgres for observability and audit trails.
- Demonstrate reliable processing by enqueueing >200 jobs and draining with clear success/failure stats.

## Architecture Overview
- **Queues:** `ingest`, `summarize`, `verify`, `embed`, `link`, `entity_extract` with explicit priority tiers (High for new releases, Normal for backfill, Low for reprocess).
- **Workers:** Node/TypeScript process using BullMQ or Python worker parity; each worker loads config, registers health checks, and reports Prometheus metrics.
- **Job Lifecycle:** Submission → Redis queue → Worker execution with exponential backoff (3 retries default) → Postgres audit row → Success or DLQ bucket.

## Workstreams & Detailed Tasks

### 1. Queue Infrastructure
1. Provision Redis connection details via env + TLS readiness for production.
2. Define BullMQ queue factories with standardized settings (attempts, backoff, concurrency, job removal policies).
3. Implement `QueueManager` helper to publish jobs and track job IDs for correlation logging.

### 2. Worker Framework
1. Scaffold base worker class (TypeScript) with hooks: `setup()`, `process(job)`, `onSuccess`, `onFailure`.
2. Add structured logging (pino or structlog) including job ID, source, retry count.
3. Expose `/health` endpoint per worker and register to monitoring stack.
4. Support graceful shutdown (SIGINT/SIGTERM) ensuring inflight jobs finish or re-queue.

### 3. Job Tracking & Persistence
1. Create `job_runs` table (if not already) capturing job name, payload summary, status, duration, error payloads.
2. Write ORM helpers to insert job rows at start/end; tie ingestion-run ID to downstream jobs for lineage.
3. Build CLI/endpoint to list recent jobs, filter by status, inspect errors.

### 4. Dead Letter & Retry Strategy
1. Configure BullMQ DLQ using dedicated queues (e.g., `<queue>:failed`).
2. Implement admin script to replay DLQ jobs after fixes with throttling.
3. Document retry policies per job type (e.g., summarize: 5 attempts, verify: 2 attempts due to cost).

### 5. Observability & Alerts
1. Add Prometheus counters/gauges for queue depth, job durations, failure counts.
2. Emit structured logs and send Sentry events when failure rate exceeds threshold.
3. Define alert thresholds (queue backlog >100, failure rate >5%) for Week 4’s dashboard wiring.

## Day-by-Day Timeline
- **Day 1:** Implement queue factories and base worker scaffolding; smoke-test with dummy jobs.
- **Day 2:** Persist job lifecycle in DB, build CLI/API to inspect jobs.
- **Day 3:** Add DLQ handling, replay tooling, and finalize retry policies per job type.
- **Day 4:** Instrument metrics/logging, wire health checks, run load test (200+ jobs).
- **Day 5:** Stabilize, fix race conditions, and document runbooks for operators.

## Validation Checklist
- Enqueue synthetic job burst (≥200) and observe workers draining without crashes.
- DB `job_runs` shows accurate counts/durations; failed jobs land in DLQ with retriable data.
- Health checks and metrics endpoints return expected data; Grafana shows queue depth.
- CLI/admin endpoint can pause/resume queues and replay DLQ items.

## Risks & Mitigations
- **Redis outages:** Implement connection retry/backoff and auto-pausing of enqueueing when Redis unavailable.
- **Worker memory leaks:** Containerize workers with resource limits and liveness probes.
- **Message loss:** Enable BullMQ persistence (default) and avoid `removeOnComplete` until results stored.
- **Complex debugging:** Include payload hashes and ingestion IDs in logs for correlation.

## Deliverables
- Queue/worker codebase (likely `workers/` directory) with README.
- Database schema updates for job tracking + migrations.
- CLI/API endpoints for job management.
- Load-test report or log excerpt proving reliable job processing.
