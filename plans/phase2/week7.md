# Week 7: Fallbacks & Guardrails – Execution Playbook

## Mission & Success Criteria
- Implement deterministic fallback summarization (TF-IDF extractive) and verification bypass that keep pipeline running when LLMs unavailable or budgets exceeded.
- Integrate automatic circuit breaker actions that switch workflows to fallbacks and emit alerts without manual intervention.
- Deploy content quality filters detecting speculation, missing citations, or schema drift, feeding into manual review queues.
- Demonstrate graceful degradation across at least three failure drills (LLM outage, malformed output, cost overrun) with documented outcomes.

## Workstreams & Detailed Tasks

### 1. Extractive Summarization Fallback
1. Build TF-IDF/keyword-based summarizer that selects representative sentences per release, constrained to target token limits.
2. Include deterministic “why it matters” heuristics (e.g., highlight sentences mentioning ministers, budgets, deadlines).
3. Tag fallback summaries in DB, exposing metadata so downstream consumers know confidence level.
4. Benchmark runtime and ensure cached results invalidate when LLM summaries later succeed.

### 2. Circuit Breaker Automation
1. Extend spend trackers with sliding windows (hourly/daily/monthly) and thresholds that trigger fallback mode per operation type.
2. Implement state machine in Redis indicating `OPEN`, `HALF_OPEN`, `CLOSED` per job type, with auto-reset timers.
3. Provide admin override controls plus Slack/email alerts when breakers trip or reset.
4. Log reason codes and affected releases for postmortems.

### 3. Content Quality Filters & Guardrails
1. Define set of automatic checks: missing citations, unsupported claims, hedging language, PII detection, tone compliance.
2. Implement deterministic regex/keyword scanners followed by lightweight ML heuristics where needed (no LLM usage to keep costs low).
3. Integrate filters into summarization pipeline; failing summaries either retried, downgraded to fallback, or flagged.
4. Surface quality metrics (pass rate, most common failure reason) to monitoring dashboards.

### 4. Failure Scenario Testing & Runbooks
1. Script simulated outages: disable OpenAI credentials, force circuit breaker due to fake spend, inject malformed JSON outputs.
2. Observe that pipeline switches to fallback summarizer, verification skip, and guardrail logs without human intervention.
3. Capture timings, user-facing behavior (API responses, email digests) and ensure SLA messaging is clear.
4. Update runbooks describing detection, mitigation steps, and reprocessing instructions once primary systems return.

## Day-by-Day Timeline
- **Day 1:** Implement extractive summarizer + metadata tagging, wire into pipeline as optional path.
- **Day 2:** Build circuit breaker automation with Redis state + alerts.
- **Day 3:** Add content quality filters and integrate with summary post-processing.
- **Day 4:** Develop failure drills, simulate outages, and fix observed gaps.
- **Day 5:** Document guardrail behavior, update runbooks, and produce report summarizing drill outcomes.

## Validation Checklist
- Circuit breaker transitions to fallback mode within one job cycle when spend threshold reached, and auto-resets after cooldown.
- Fallback summaries generated for test releases look coherent (validated by manual sample) and are clearly labeled downstream.
- Quality filters catch intentionally injected issues (missing citations, speculation) and create `content_flags` entries.
- Failure drill report documents at least three scenarios with timestamps, alerts, and remediation steps.

## Risks & Mitigations
- **Fallback quality too low:** Iterate on sentence selection heuristics, add domain-specific ranking, and flag fallback outputs for manual review.
- **Circuit breaker oscillation:** Add hysteresis/cooldown windows and manual override ability to prevent flapping.
- **Alert fatigue:** Tune thresholds, batch notifications, and provide context (affected releases) in alerts.
- **Drill coverage gaps:** Schedule recurring simulations; treat missing runbooks as blockers before moving to Week 8.

## Deliverables
- Extractive summarization fallback implementation + documentation.
- Circuit breaker automation with monitoring + alert hooks.
- Content quality filter suite + metrics dashboard panels.
- Failure drill report stored in `docs/runbooks/week7-fallbacks.md` with follow-up tasks.
