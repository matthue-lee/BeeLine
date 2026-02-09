# Week 1: Infrastructure Setup – Execution Playbook

## Mission & Success Criteria
- Stand up a reproducible local environment where `docker-compose up` launches Postgres, Redis, Meilisearch, and the ingestion API.
- Baseline observability stack (Sentry client, Prometheus metrics endpoint) is wired into every service and emits sample events.
- Alembic migrations can create the full schema on a fresh database and are idempotent.
- Hosting platform decision (Fly.io vs Railway vs AWS) documented with trade-offs and next-step actions.

## Workstreams & Detailed Tasks

### 1. Docker Compose Stack
1. Inventory required services → Postgres 16, Redis 7, Meilisearch 1.11, ingestion API, placeholder worker.
2. Write `docker-compose.yml` with health checks, persistent volumes, and resource caps.
3. Add `.env.docker` template (ports, passwords) and document overrides.
4. Create bootstrap scripts (`scripts/dev_up.sh`, `scripts/dev_down.sh`) to avoid manual compose commands.
5. Verify data directories mount correctly on macOS/Linux and support hot reload for the API container.

### 2. Database Schema & Migrations
1. Translate `beeline_ingestor.models` into Alembic migrations (entities, mentions, releases, link tables, etc.).
2. Enable autogeneration but keep manual revisions for repeatability; enforce naming conventions.
3. Write `scripts/reset_db.sh` that drops DB, runs migrations, seeds lookup tables (ministers, ministries, policies).
4. Configure SQLAlchemy URI injection for Docker/Postgres vs. local SQLite fallback.
5. Run `alembic upgrade head` inside the API container and from host to ensure parity.

### 3. Monitoring Foundations
1. Instrument FastAPI/Flask app with OpenTelemetry or Prometheus client, exposing `/metrics`.
2. Add Sentry SDK with DSN pulled from env; ship at least one synthetic event.
3. Provide Grafana dashboard JSON skeleton and a `docker-compose` service for local Prometheus + Grafana if feasible.
4. Define baseline logs (structured JSON) and log rotation strategy.

### 4. Hosting Decision Record
1. Capture requirements (cost ceiling, regional availability, managed Postgres, autoscaling needs).
2. Build comparison grid for Fly.io, Railway, AWS (setup time, cost, ops burden).
3. Spike deploy of a “hello world” container to the preferred platform to validate networking and secrets.
4. Document decision + next steps in `docs/decision-records/week1-hosting.md`.

## Day-by-Day Timeline
- **Day 1:** Draft Docker Compose, validate containers start, wire `.env` management.
- **Day 2:** Implement Alembic migrations, migration scripts, and DB reset tooling.
- **Day 3:** Integrate monitoring hooks (metrics endpoint + Sentry), smoke-test alerts.
- **Day 4:** Evaluate hosting options, run spike deployment, finalize decision record.
- **Day 5 (buffer):** Fix integration issues, polish documentation, run end-to-end `docker-compose up` validation.

## Validation Checklist
- `docker-compose up --build` succeeds from a clean clone and API responds at `localhost`.
- `alembic downgrade base && alembic upgrade head` runs without manual edits.
- Metrics endpoint exposes release/worker counts; Sentry dashboard shows at least one captured exception.
- Decision record approved (self or reviewer) with clear rationale.

## Risks & Mitigations
- **Container drift across hosts:** Pin image versions and use Dev Containers CI check.
- **Migration rot:** Add CI job that runs migrations on an empty Postgres instance for every PR.
- **Monitoring noise:** Start with low sampling rate and wrap instrumentation behind feature flags.
- **Hosting indecision:** Time-box spike to one day and capture unknowns rather than stalling.

## Deliverables
- `docker-compose.yml`, `.env.example`, helper scripts.
- Alembic migrations + README instructions.
- Monitoring instrumentation (Sentry config, `/metrics` endpoint) with documentation.
- Hosting decision record summarizing choice, costs, risks.
