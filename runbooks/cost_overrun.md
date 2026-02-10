# Runbook: Cost Overrun / Circuit Breaker Open

1. **Detect:** Alert from Sentry (`breaker_open`) or Grafana panel spikes.
2. **Verify spend:** `curl http://ingestion-api:8000/costs?hours=24` to confirm offending operation.
3. **Pause queues:** `docker compose scale queue-worker=0` or `redis-cli` to pause target BullMQ queue.
4. **Fallback:** Ensure ingestion uses extractive summaries / cached news links while breaker is open.
5. **Remediate:**
   - Inspect recent prompt changes/traffic.
   - If acceptable, increase env limits temporarily; otherwise keep breaker open until next budget window.
6. **Reset:** Once safe, run `./scripts/circuit_breaker_admin.py summarize reset`.
7. **Postmortem:** Document cause in issue tracker; adjust limits or prompt usage as needed.
