# Week 4: Cost Controls & Monitoring – Execution Playbook

## Mission & Success Criteria
- Implement real-time cost tracking and circuit breaker logic for every LLM/News API call.
- Ship dashboards/alerts (Grafana + Slack/email) that visualize spend, queue health, and job errors.
- Build labeled evaluation datasets (50 summaries, 50 IR queries) to support nightly QA.
- Deliver operational documentation/runbooks for core incident types.

## Workstreams & Detailed Tasks

### 1. Cost Instrumentation & Tracking
1. Wrap all OpenAI/News API clients with a `CostTracker` that records tokens, latency, and estimated USD spend per call.
2. Persist call-level data into `llm_calls` table (existing in data model) with job linkage.
3. Aggregate hourly/daily spend into Redis counters and nightly `daily_costs` rollup for dashboards.
4. Provide CLI/API endpoints to query spend by operation type, time window, and prompt version.

### 2. Circuit Breakers & Fallbacks
1. Implement sliding-window budgets (hour/day/month) stored in Redis and configurable via env.
2. When 80/90/100% thresholds hit, automatically: log, emit Sentry alert, pause offending queues, and switch to fallback (extractive summary, cached news links, etc.).
3. Add admin override that can temporarily raise limits or resume queues after review.
4. Include automated self-healing to re-close breakers once spend recovers or after cooldown window (e.g., 30 minutes).

### 3. Monitoring & Alerting Stack
1. Deploy Prometheus + Grafana stack (if not already from Week 1) or connect to Grafana Cloud.
2. Export metrics: queue depth, job failure rate, cost per job type, API latency, ingestion throughput.
3. Build dashboard panels: overview, cost trends, queue health, error drill-down.
4. Configure alerts routed to Slack/email for critical (circuit open, high failure) and warning (queue backlog, high spend trajectory) levels.

### 4. Evaluation Dataset Creation
1. Select 50 representative releases for manual gold summaries + metadata; store in version-controlled JSON/Parquet.
2. Select 50 releases for IR evaluation with labeled relevant articles (3-point scale) stored similarly.
3. Document annotation guidelines, tooling (e.g., Notion/Google Sheet), and inter-annotator agreement process.
4. Build ingestion script that loads these datasets into S3/MinIO and DB tables ready for nightly eval job (Phase 4).

### 5. Runbooks & Documentation
1. Draft incident response guides: LLM outage, cost overrun, queue backlog, digest failure.
2. Include checklists, escalation paths, and mitigation scripts.
3. Publish docs in `runbooks/` with links from README.

## Day-by-Day Timeline
- **Day 1:** Implement cost tracking wrappers + persistence; validate with mocked API calls.
- **Day 2:** Build circuit breaker logic, fallbacks, and admin overrides; write tests.
- **Day 3:** Stand up dashboards, wire metrics exporters, configure alert channels.
- **Day 4:** Create evaluation datasets, document process, store in repo/storage.
- **Day 5:** Finalize runbooks, perform chaos exercises (simulate breaker trigger, queue backlog) to prove system response.

## Validation Checklist
- Cost dashboard shows real-time hourly/daily spend with <5 min lag.
- Triggered circuit breaker automatically pauses target queue and logs event; manual override resumes safely.
- Alerts fire when spend exceeds 80/90% thresholds and when queue backlog >100 jobs.
- Evaluation datasets exist in repo/storage with schema definitions and are referenced by nightly job config.
- Runbooks reviewed and cover at least four incident types with step-by-step remediation.

## Risks & Mitigations
- **Cost underreporting:** Cross-check OpenAI usage dashboards against internal metrics weekly; add unit tests around cost formulas.
- **Alert fatigue:** Implement suppression windows and classify alerts (info/warn/critical) to avoid noise.
- **Annotation bottleneck:** Schedule time with domain expert early; script template to speed manual labeling.
- **Circuit breaker bugs blocking work:** Provide manual bypass flag and thorough integration tests before enabling in production.

## Deliverables
- Cost tracking middleware + persistence schema updates (if needed).
- Circuit breaker module with documented env vars and admin CLI.
- Grafana dashboard JSON + alerting rules stored in repo.
- Evaluation datasets + documentation.
- Runbooks covering incidents and escalation procedure.
