# Evaluation Datasets (Week 4)

## Summary Gold Set
- File: `datasets/summary_gold.jsonl`
- 50 releases with gold summaries, "why it matters", and claim/evidence pairs.
- Fields: `release_id`, `published_at`, `summary_short`, `summary_why_matters`, `claims[]`, `annotator`, `prompt_version`.

## IR Labels
- File: `datasets/ir_labels.jsonl`
- 50 releases with relevance labels for 3 associated articles each (0=Irrelevant, 1=Related, 2=Highly Relevant).
- Fields: `release_id`, `query`, `labels[] {article_id, rating, notes}`.

## Usage
1. Load into Postgres via `COPY` or ingest script to power nightly evaluation job.
2. Store raw files in object storage (MinIO/S3) for reproducibility.
3. Update quarterly; track versions via Git history+migration table.
