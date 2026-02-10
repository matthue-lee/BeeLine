# Week 5 Report

## Day 1 – Prompt Templates
- Added `prompt_templates` table/model/migration with CLI (`scripts/prompt_templates.py`) to manage
  versions, metadata, and traffic allocation for A/B tests.

## Day 2 – LLM Client & Validation
- Implemented `LLMClient` wrapper that loads active templates, generates JSON summaries (simulated for
  local dev), validates them via Pydantic schema, and records cost metrics via `CostTracker` + circuit
  breaker hooks.

## Day 3 – Summary Persistence & API
- Introduced `SummaryService` plus ingestion-pipeline hooks so each release produces a structured
  summary stored in `summaries` table (with model/prompt version metadata). `/releases` now returns
  summary payloads alongside links/content.

## Day 4 – Guardrails & Overrides
- Added guardrail cleaning (hedging removal), manual override CLI (`scripts/summary_override.py`), and
  batch generation script (`scripts/generate_summaries.py`). Prompt routing honors traffic allocation
  percentages, enabling future A/B tests.

## Day 5 – QA / Batch Run (script)
- `scripts/generate_summaries.py --limit 50` processes batches for QA. Operators can review outputs
  via `/releases` or DB queries and note stats in this report.
