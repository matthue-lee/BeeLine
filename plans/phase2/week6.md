# Week 6: Verification System – Execution Playbook

## Mission & Success Criteria
- Extract claims from summaries, retrieve supporting evidence, and record verification scores ≥85% accuracy on test set.
- Provide automated flagging for unsupported claims and surface status in admin tools.

## Workstreams & Detailed Tasks

### 1. Claim Extraction
1. Extend summarization worker to output normalized claims array.
2. Build deterministic claim parser + store in `claims` table with summary linkage.

### 2. Evidence Retrieval
1. Implement retrieval helper (BM25 + chunked release text) to fetch candidate sentences.
2. For each claim, run QA-style LLM prompt to confirm support; capture evidence text + confidence.

### 3. Verification Worker
1. Add `verify` queue/worker that processes stored claims, records result in `claim_verifications` table.
2. Integrate CostTracker + breaker for verification LLM calls.
3. Auto-flag unverified claims (`content_flags` entry) for manual review.

### 4. Metrics & Reporting
1. Compute per-summary verification score (supported claims / total).
2. Dashboard panel + `/jobs` filter for verification jobs.
3. Configure nightly report to list low-confidence summaries.

## Day-by-Day Timeline
- **Day 1:** Claim storage schema, parser integration.
- **Day 2:** Retrieval module + candidate sentence selection.
- **Day 3:** Verify worker + LLM prompt; persist results.
- **Day 4:** Flagging, admin UI/API updates, metrics.
- **Day 5:** Accuracy evaluation on labeled set; document gaps.

## Validation Checklist
- ≥85% of claims in evaluation set have correct support sentences.
- Verification jobs recorded in `job_runs`; DLQ handling works.
- Unsupported claims produce `content_flags` entries.
- Dashboard/alerts reflect verification failure spikes.

## Risks & Mitigations
- **Ambiguous claims:** Add deterministic heuristics + human override queue.
- **Retrieval misses:** Combine heuristics (BM25 + embeddings) and re-run when confidence low.
- **Cost overruns:** Lower attempts or switch to cheaper model for verification.

## Deliverables
- Claim storage + parser.
- Verification worker + retrieval pipeline.
- Metrics/flags + documentation of accuracy results.
