# Week 5: Summarization Pipeline – Execution Playbook

## Mission & Success Criteria
- Prompt template system persists versioned instructions with semantic versioning, rollout flags, and audit metadata.
- GPT-4o-mini integration produces structured JSON summaries (short brief, why-it-matters, claims[], citations[]) with schema validation and retry logic.
- At least 50 historical releases summarized end-to-end with provenance (model, prompt version, token/cost stats) stored in Postgres and cached in Redis.
- Cost controls enforce circuit breaker checks on every LLM call and expose spend metrics to monitoring stack.

## Context & Dependencies
- **Prerequisite components:** Week 1 infrastructure (Docker, Postgres, Redis), Week 2 ingestion pipeline with cleaned releases, Week 3 job queue framework, Week 4 cost monitoring primitives.
- **Upstream data:** canonical `releases` rows with cleaned text, minister metadata, and ingestion timestamps. Backfill dataset of ≥100 releases for benchmarking.
- **Downstream consumers:** verification worker (Week 6), cross-linking/search (Week 8), daily digest/email service, mobile app content APIs.
- **Tooling:** Alembic for migrations, FastAPI admin endpoints, BullMQ job orchestration, Redis caching, Grafana dashboards.

## Stakeholders & Communication
- **Primary owner:** Backend/AI engineer implementing summarization services.
- **Reviewers:** Product owner for prompt tone/voice, cost owner for budget guardrails, ops engineer for monitoring hooks.
- **Cadence:** Daily async status in project channel, mid-week live review of sample summaries, end-of-week readout covering metrics + follow-ups.
- **Artifact updates:** `docs/prompts/CHANGELOG.md`, `docs/runbooks/summarization.md`, Grafana dashboard panels for LLM spend + throughput.

## Workstreams & Detailed Tasks

### 1. Prompt Template Management
1. Design `prompt_templates` table: fields for semantic version, purpose (summarization), template body, sampling parameters, rollout percentage, status.
2. Build admin CLI/CRUD endpoints to create, publish, deprecate templates while logging author + change notes.
3. Implement prompt rendering utility that injects release metadata, guidelines, and deterministic instructions before dispatch.
4. Store prompt version reference on each summary row for traceability and later A/B analysis.

### 2. LLM Invocation Layer
1. Create `LLMClient` abstraction handling authentication, retries with exponential backoff, timeout budgets, and structured logging of latency/tokens.
2. Enforce circuit breaker and hourly/daily spend checks prior to every call; fail closed with documented error reason.
3. Implement rate limiting/batching (Bottleneck or asyncio semaphore) to keep throughput predictable and OpenAI limits respected.
4. Record each invocation in `llm_calls` with context (release_id, template_id, purpose) and persist streaming responses to avoid losing partial data.

### 3. Structured Output Validation
1. Define Zod/Pydantic schema capturing short summary, why-it-matters paragraph, bullet claims, citation references, guardrail flags.
2. Parse LLM output via JSON mode; if invalid, attempt automatic correction prompt, else emit fallback record for manual review queue.
3. Normalize claims/citations by trimming whitespace, enforcing sentence case, attaching canonical cite IDs referencing raw release sentences.
4. Embed validation errors + remediation actions in `job_runs` logs for observability and QA audits.

### 4. Summary Persistence & Caching
1. Extend `summaries` table to hold structured payload, verification placeholder fields, prompt version, timestamps, and quality scores.
2. Persist raw LLM response alongside cleaned version for reproducibility; store cost metrics used for dashboards.
3. Cache final summaries in Redis for 24 hours with invalidation hook triggered when release content changes or manual overrides occur.
4. Expose FastAPI endpoint (internal) to retrieve summary plus metadata for downstream workers (verification, email digest).

## Day-by-Day Timeline
- **Day 1:** Model `prompt_templates` schema, migrations, and CRUD surfaces; document versioning rules and establish naming/approval workflow.
- **Day 2:** Implement LLM client with rate limits, circuit breaker integration, structured logging, and unit tests covering retry paths.
- **Day 3:** Build schema validation + remediation pipeline; wire failures into content flag queue and add alert thresholds.
- **Day 4:** Persist summaries with provenance + caching; add API/CLI inspection utilities; update Grafana panels.
- **Day 5:** Process ≥50 releases, review sample outputs, tune prompts, finalize documentation, and capture lessons in `docs/prompts/week5-report.md`.

## Validation Checklist
- Creating/updating prompt templates requires explicit version bump and writes audit log entries.
- `summaries` records include prompt version, token counts, cost, and link back to source release.
- JSON schema validation catches malformed outputs and logs remediation attempts; <2% require manual intervention during test run.
- Circuit breaker metrics show LLM spend tracked per call with guardrails enforced.
- API/CLI retrieval of summaries completes <1s for cached results.

## Risks & Mitigations
- **Prompt drift / degraded quality:** Maintain small rollout percentages for new prompts, capture qualitative review notes before full release.
- **Schema-breaking outputs:** Provide self-healing retry prompts and escalate to manual queue after two failures to avoid stuck jobs.
- **Cost overruns:** Instrument per-operation spend dashboards; cap concurrency until real usage data collected.
- **Data loss during retries:** Use idempotent job IDs and persist intermediate LLM responses before validation to allow replay.

## Deliverables
- `prompt_templates` schema + management tooling.
- LLM client with cost tracking, rate limiting, and circuit breaker enforcement.
- Structured summary generation pipeline with validation + caching.
- Report documenting sample outputs, prompt tuning notes, and follow-up tasks.

## Documentation & Runbooks
- `docs/runbooks/summarization.md` outlining onboarding steps, deployment checklist, rollback procedures, and troubleshooting tips for failed jobs.
- `docs/prompts/README.md` explaining tone/voice guidelines, template format, semantic versioning policy, and review steps.
- Update monitoring playbooks with new dashboards (LLM cost per summary, throughput, error rate) and alert routing instructions.

## Open Questions & Follow-Ups
- Confirm whether prompt templates require localization variants (e.g., stakeholder-specific voice) before Week 9 mobile work.
- Decide on storage of raw vs. redacted release text within prompt renderer for privacy or licensing constraints.
- Align with Week 6 verification team on claim schema to ensure compatibility before extraction logic ships.
