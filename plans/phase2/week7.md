# Week 7: Fallback Mechanisms & Guardrails – Execution Playbook

## Mission & Success Criteria
- Ensure summarization/verifier/search pipelines degrade gracefully when budgets, APIs, or quality gates fail.
- Implement automated fallback paths (extractive summary, cached news links, manual review flags) and test failure scenarios.

## Workstreams & Detailed Tasks

### 1. Extractive Summaries & Templates
1. Build TF-IDF/lead paragraph extractor for releases.
2. Trigger fallback when circuit breaker opens or LLM returns malformed output; store reason in provenance.

### 2. Budget & Circuit Integration
1. Connect circuit-breaker signals to queue pausing/resumption.
2. Add admin CLI/API to override or extend budgets temporarily with audit logging.

### 3. Guardrails & Quality Filters
1. Implement post-process filters (hedging removal, banned phrases, citation validation).
2. Auto-create `content_flags` for low verification score, high fallback usage, or manual reviewer feedback.

### 4. Failure Scenario Testing
1. Simulate LLM downtime, Redis outage, and high-cost scenarios; document outcomes.
2. Ensure queue replay + runbooks cover each scenario.

## Day-by-Day Timeline
- **Day 1:** Extractive summary implementation + integration with pipeline.
- **Day 2:** Circuit breaker ↔ queue control hooks + admin overrides.
- **Day 3:** Guardrail filters + content flagging.
- **Day 4:** Failure scenario simulations + DLQ replay tests.
- **Day 5:** Consolidate documentation + sign-off on fallback readiness.

## Validation Checklist
- Fallback summaries produced within SLA when GPT calls are blocked.
- Circuit breaker opening pauses affected queues and resumes after manual reset.
- Guardrail violations generate content flags and appear in admin UI.
- Failure drills logged with before/after metrics.

## Risks & Mitigations
- **Fallback quality too low:** Keep summary length constraints + manual review queue.
- **Circuit misconfiguration pauses too much:** Provide per-queue overrides and alerts before shutdown.
- **Guardrails over-trigger:** Start with warning mode; adjust thresholds.

## Deliverables
- Fallback summarization module.
- Circuit breaker + queue integration with admin tooling.
- Guardrail filters and scenario test report.
- Documentation updates to monitoring + runbooks.
