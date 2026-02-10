# Runbook: Queue Backlog

1. **Detect:** Grafana alert `QueueBacklogHigh` or `bullmq` showing >100 waiting jobs.
2. **Inspect:**
   - `docker compose logs queue-worker`
   - `/jobs?status=failed` for repeated failures.
3. **Actions:**
   - Temporarily scale workers: `docker compose up -d --scale queue-worker=3`.
   - Re-enqueue failed jobs using `npm run replay-failed`.
   - Pause ingestion if backlog persists to prevent overload.
4. **Root Cause:** Determine if downstream API latency, DB lock, or bad payloads caused slowdown.
5. **Resolution:** Once backlog <20, scale workers back and document fix.
