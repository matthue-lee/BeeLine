# Week 6: Verification System – Execution Playbook

## Mission & Success Criteria
- Automatically extract structured claims from summaries and score factual support using source sentences.
- Achieve ≥85% verification accuracy on labeled evaluation set (50 examples) with confidence scores recorded.
- Every claim in production summaries links to at least one supporting evidence snippet or is flagged for review.
- Verification outputs (scores, rationales, flags) stored in Postgres and fed into monitoring dashboards.

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
- **Day 1:** Model `claims` + `claim_verifications` schema, implement extraction logic, seed with existing summaries.
- **Day 2:** Build evidence retrieval service (sentence chunking, hybrid search, caching) and benchmark latency.
- **Day 3:** Implement verification prompt + LLM workflow, store results with provenance.
- **Day 4:** Wire flagging/alerting + admin inspection surfaces.
- **Day 5:** Run evaluation set, tune thresholds to exceed 85% accuracy, and document findings in `docs/verification/week6-report.md`.

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
