# Runbook: BeeLine Operations Overview

This document gives on-call engineers a single reference for diagnosing and resolving issues in the BeeLine stack. Use it alongside the scenario-specific runbooks located in `runbooks/`.

## 1. First Response Checklist

1. **Acknowledge alert** in Slack/Email and note timestamp.
2. **Identify service** impacted (API, scheduler, BullMQ workers, cost breaker, email digest, etc.).
3. **Check dashboards** (Grafana → "BeeLine Overview") for:
   - `beeline_ingestion_runs_total`, `beeline_summary_generations_total`
   - `queue_depth_total` per queue
   - API latency/error panels
   - Cost gauge vs hourly/daily limit
4. **Inspect logs**:
   - `docker compose logs ingestion-api`
   - `docker compose logs ingestion-worker`
   - `docker compose logs queue-worker`
   - Alloy/Grafana Explore for correlated traces
5. **Determine scenario** using the quick reference table below and follow linked runbook.

## 2. Quick Reference by Symptom

| Symptom | Key Signals | Runbook |
| --- | --- | --- |
| Waiting jobs >100 or DLQ growth | Grafana alert `QueueBacklogHigh`, `queue_job_results_total{status='failed'}` spikes | `runbooks/queue_backlog.md` |
| LLM calls failing or provider outage | Grafana alert on failures, OpenAI status red, circuit breaker open | `runbooks/llm_outage.md` |
| Spend exceeds budget or breaker triggered unexpectedly | `/costs` endpoint spikes, Redis breaker keys set | `runbooks/cost_overrun.md` |
| Daily digest missing or late | Digest GitHub Action failed, `/jobs?job_type=digest` errors, SendGrid/Resend alerts | `runbooks/digest_failure.md` |

## 3. Environment & Access

- **Docker Compose:** `./scripts/dev_up.sh` to start, `./scripts/dev_down.sh` to stop.
- **Key services:**
  - `ingestion-api` (Flask, port `${INGESTION_API_PORT:-8000}`)
  - `ingestion-worker` (Python scheduler, internal metrics at `http://ingestion-worker:9101/metrics`)
  - `queue-worker` (BullMQ workers + metrics `http://localhost:9100/metrics`)
  - `redis`, `postgres`, `meilisearch`, `alloy`
- **Credentials:** `.env` holds DB/Redis/API secrets. Verify before running destructive commands.

## 4. Observability Cheat Sheet

- **Metrics endpoints:**
  - API: `curl http://localhost:8000/metrics`
  - Queue worker: `curl http://localhost:9100/metrics`
  - Scheduler: `docker compose exec ingestion-worker curl -sf http://localhost:9101/metrics`
- **Important metrics:**
  - `queue_depth_total{queue, state}` – backlog/active jobs
  - `queue_job_results_total{queue, status}` – success/failure rates
  - `beeline_ingestion_runs_total{status}` – ingestion health
  - `beeline_summary_generations_total{status}` – summarization outcomes
  - `beeline_http_request_seconds_bucket` + `beeline_http_requests_total` – API latency/throughput
  - `beeline_rss_requests_total{status!='200'}` – RSS error rate
  - Cost metrics via `/costs` endpoint (hourly/daily spend breakdown)
- **Logs:** Access through Docker logs or Grafana Alloy (Loki) queries. Filter by container label or `job` field.

## 5. Incident Workflow

1. **Stabilize:** Apply immediate mitigations (pause queues, enable fallbacks, notify users) to stop impact.
2. **Diagnose:** Use metrics/logs/DB to find faulty component. Correlate with recent deployments or config changes.
3. **Remediate:** Roll back offending change, replay failed jobs, adjust budgets, or restart services as needed.
4. **Recover:** Ensure queues drain, costs normalize, and API latency returns to baseline. Re-enable disabled components incrementally.
5. **Communicate:** Post updates in #ops channel or incident doc; notify stakeholders (digest subscribers, admins) if user impact occurred.
6. **Postmortem:** File GitHub issue with root cause, timeline, fixes, and follow-up actions.

## 6. Command Snippets

- **Pause/scale workers:** `docker compose up -d --scale queue-worker=0` (pause) or `=3` (scale up temporarily).
- **Replay DLQ jobs:**
  ```bash
  cd workers
  npm run replay-failed -- 20
  ```
- **Inspect failed jobs:** `curl http://localhost:8000/jobs?status=failed&limit=20`
- **Check costs:** `curl http://localhost:8000/costs?hours=24`
- **Circuit breaker admin:** `./scripts/circuit_breaker_admin.py summarize open|reset`
- **Trigger ingestion manually:** `curl -X POST http://localhost:8000/ingest/run -H 'Content-Type: application/json' -d '{"since":"2024-04-01T00:00:00Z"}'`

## 7. Escalation & Contacts

- **Primary on-call:** Refer to Ops calendar / Slack topic `#ops-schedule`.
- **Secondary:** Tech lead or senior engineer noted in schedule.
- **Vendors:** OpenAI status page, Resend/SendGrid status, Fly.io status.
- **External comms:** If user-visible downtime >1 hour, coordinate with product owner for updates.

## 8. Related Documents

- `runbooks/queue_backlog.md`
- `runbooks/cost_overrun.md`
- `runbooks/llm_outage.md`
- `runbooks/digest_failure.md`
- `docs/backend_handbook.md`
- `docs/queue-system.md`
- `monitoring/README.md`

Use this runbook as the entry point: start here during incidents, then dive into the specific playbook for the detected scenario.

