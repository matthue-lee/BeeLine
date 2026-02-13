# Week 6: Verification System – Execution Playbook

## Mission & Success Criteria
- Automatically extract structured claims from summaries and score factual support using source sentences.
- Achieve ≥85% verification accuracy on labeled evaluation set (50 examples) with confidence scores recorded.
- Every claim in production summaries links to at least one supporting evidence snippet or is flagged for review.
- Verification outputs (scores, rationales, flags) stored in Postgres and fed into monitoring dashboards.

## Context & Dependencies
- **Prerequisites:** Week 5 summarization pipeline (structured JSON summaries + prompt metadata) and ingestion storing raw release text with sentence indexes. pgvector or another embedding store must be available (Week 8 work may be partially reused).
- **Existing tools:** `SummaryPayload` structure, `content_flags` table, Prometheus metrics registry, Redis cache, Sentry alerting. Ensure spaCy sentence splitter or equivalent deterministic tokenizer is available for evidence chunking.
- **Downstream consumers:** Admin panel (Week 14) will surface verification outcomes; evaluation suite (Week 13) depends on these metrics for nightly regressions.

## Stakeholders & Communication
- **Owner:** Backend/AI engineer implementing claims + verification.
- **Reviewers:** Product (definition of “supported claim”), Ops (alert thresholds / runbooks), Data lead (evaluation dataset).
- **Cadence:** Daily async status in project channel, mid-week sync demo of verification UI/API, end-of-week write-up (`docs/verification/week6-report.md`).
- **Artifacts:** Updated ERD, API docs for verification endpoints, Grafana dashboards/panels for pass rate + latency, runbook for reprocessing failed claims.

## Workstreams & Detailed Tasks

### 1. Claim Extraction Pipeline
1. Define schema for `claims` table capturing text, category (policy/action/impact), originating summary_id, and ordering.
2. Implement deterministic parser that reads structured summary JSON and emits normalized claim records with stable IDs.
3. Add heuristics to merge duplicate claims across prompt reruns and retain history for auditing.
4. Surface extraction statistics (claims per summary, dropped claims) in Prometheus metrics for quality monitoring.

### 2. Evidence Retrieval Layer
1. Build retrieval utility that splits cleaned release text into sentences/chunks annotated with source positions and embeddings (reuse ingestion artifacts).
2. Implement hybrid search (BM25 + embedding cosine) to fetch top-k candidate sentences per claim with latency <1s.
3. Provide fallback when embeddings are missing (BM25 only) and log coverage gaps for data backfill tasks.
4. Cache retrieval results per claim to avoid rework during verification retries.

### 3. LLM Verification Workflow
1. Design prompt template for claim support check (question + candidate sentences) with explicit JSON verdict schema (supported/contradicted/insufficient + rationale).
2. Route verification calls through existing LLM client with dedicated purpose tag for cost accounting and concurrency limits.
3. Establish confidence scoring logic (e.g., supported probability) and threshold for auto-flagging (<0.7 recommended).
4. Persist verification attempts, verdicts, rationales, selected evidence sentences, and latency metrics in `claim_verifications` table.

### 4. Flagging & Manual Review Hooks
1. Integrate with `content_flags` to open review tasks when claims lack support, contradict sources, or verification fails twice.
2. Provide admin dashboard/API endpoints to inspect flagged claims, override verdicts, or attach manual notes.
3. Extend notification pipeline (Slack/email) to alert when verification pass rate drops below threshold or backlog exceeds SLA.
4. Document runbook for reprocessing claims when prompt versions change or new evidence data arrives.

## Day-by-Day Timeline
- **Day 1:** Model `claims` + `claim_verifications` schema (Alembic migration, ORM, indexes) and implement claim extraction job; backfill existing summaries to populate baseline data.
- **Day 2:** Build evidence retrieval microservice (sentence chunking, embedding cache, hybrid search) and record latency metrics; add Prometheus counters for retrieval hits/misses.
- **Day 3:** Implement LLM verification workflow with structured outputs + circuit breaker budgets; persist verdicts/citations and expose internal API endpoints.
- **Day 4:** Wire flagging + alerting (content flags, Slack/email) and create admin inspection endpoints/CLI for overrides; add dashboard panels showing pass rates + backlog.
- **Day 5:** Run evaluation set, tune thresholds to hit ≥85% accuracy, document results in `docs/verification/week6-report.md`, and handoff runbook for reprocessing/failure scenarios.

## Validation Checklist
- Every summary processed post-week6 has ≥1 claim with associated verification verdict.
- Claims lacking supporting evidence automatically create `content_flags` entries within same job run.
- Verification results include supporting sentence IDs and are queryable via API.
- Evaluation dataset reports ≥85% accuracy and metrics posted to monitoring dashboard.
- Alert triggers when verification pass rate dips below configured threshold.

## Risks & Mitigations
- **Slow retrieval/verification:** Batch claims, reuse cached embeddings, and cap per-summary concurrency.
- **LLM misclassification:** Maintain calibration dataset, periodically retrain thresholds, and allow manual overrides.
- **Evidence gaps:** Monitor missing sentence chunks and build backlog tasks for ingestion fixes.
- **Cost spikes:** Share circuit breaker budgets between summarization and verification with separate quotas.

## Deliverables
- Claim extraction + verification schemas and services.
- Hybrid evidence retrieval utility with caching + metrics.
- Verification prompt templates, accuracy report, and tuning notes.
- Alerting + manual review workflow documentation.

## Documentation & Runbooks
- `docs/verification/week6-report.md` summarizing accuracy, latency, costs, lessons learned.
- `docs/runbooks/claims_verification.md` covering incident response (LLM down, retrieval failure, backlog, schema updates).
- Update API docs with verification endpoints and link structure; add Grafana dashboard JSON panels for pass rate/latency.

## Open Questions & Follow-Ups
- Do we need separate verification prompt versions per portfolio/ministry or is one template sufficient?
- Should unsupported claims automatically suppress publication or merely flag? Confirm SLA with product/ops.
- Clarify retention: how long to keep raw verification conversations vs summarized outcome for compliance.
