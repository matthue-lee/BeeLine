# Week 5: Summarization Pipeline – Execution Playbook

## Mission & Success Criteria
- Deliver a DB-backed prompt template/versioning system powering GPT-4o-mini summarization.
- Generate structured JSON summaries (short + why-it-matters + claims/citations) with validation and storage.
- Process ≥50 real releases through the LLM pipeline with logged costs + verification handoff.

## Workstreams & Detailed Tasks

### 1. Prompt Template System
1. Create `prompt_templates` table (fields: name, version, body, metadata, active flag).
2. Build admin CLI to list/create/promote templates; store in repo for code review.
3. Add routing logic: 90% traffic uses stable version; 10% routed to experimental version for A/B tests.

### 2. LLM Client & Retry Wrapper
1. Implement OpenAI client wrapper with CostTracker + circuit breaker; emit structured logs per call.
2. Support configurable temperature/max tokens per template.
3. Add JSON schema validation (pydantic/Zod) before persisting; auto-reject malformed outputs.

### 3. Summary Persistence & API
1. Extend `summaries` table to include prompt version, model, cost, verification status.
2. Update ingestion pipeline to enqueue `summarize` jobs; worker fetches release text, calls LLM, stores result.
3. Expose `/releases` detail endpoint with summary payload + claims list.

### 4. Quality Validation & Guardrails
1. Add post-processing filters (remove hedging, enforce citation references).
2. Integrate claim extraction + verification queue stub for Week 6.
3. Implement manual override path: admin can replace summary text in DB.

## Day-by-Day Timeline
- **Day 1:** Prompt template schema, CLI, migrations.
- **Day 2:** LLM client wrapper + JSON validation; cost & breaker hooks.
- **Day 3:** Worker integration, DB persistence, `/releases` summary output.
- **Day 4:** Guardrails + A/B routing + manual override tooling.
- **Day 5:** Batch-run ≥50 releases, review quality, capture metrics.

## Validation Checklist
- `prompt_templates` table contains at least 2 versions; CLI can activate new version.
- `summaries` rows include prompt/model/cost metadata and pass JSON schema validation.
- Sample run processes ≥50 releases with <5% malformed outputs.
- `/releases/{id}` endpoint returns summary payload and claims array.

## Risks & Mitigations
- **JSON schema failures:** Implement auto-retry with cleaned prompt fallback; store raw output for debugging.
- **Cost spikes:** Circuit breaker from Week 4 halts summarization if needed; fallback to extractive summary.
- **Quality drift:** Keep A/B routing and manual overrides ready; schedule daily QA checks.

## Deliverables
- Prompt template schema + CLI.
- Summarize worker integration with CostTracker + breaker.
- Summary storage + API exposure.
- Batch run stats + QA notes.
