# Week 8: Search & Cross-Linking Infrastructure – Execution Playbook

## Mission & Success Criteria
- Stand up hybrid search stack (pgvector + BM25/Meilisearch) that returns relevant results for releases and articles in <500ms P95.
- Generate embeddings for releases, summaries, and news articles with scheduled backfill + incremental updates.
- Provide API endpoints and worker jobs that link each release to 3–5 related articles with similarity scores and stance classification stubs.
- Instrument retrieval quality (NDCG@3, Recall@5) using labeled dataset and expose metrics nightly.

## Workstreams & Detailed Tasks

### 1. Embedding Pipeline
1. Configure pgvector extension (if not already enabled) with optimized indexes (HNSW or IVFFlat) for `embeddings` columns.
2. Implement embedding worker that batches cleaned text chunks, calls `text-embedding-3-small`, and records token/cost stats.
3. Support backfill of historical releases/articles plus incremental updates triggered by new ingestions.
4. Cache embeddings in Redis/S3 to avoid recomputation and ensure idempotency using content hashes.

### 2. BM25 / Full-Text Search Setup
1. Configure Meilisearch (or Postgres full-text) indexes on releases and articles with tuned analyzers (English, NZ-specific stop words).
2. Define ingestion pipeline that pushes normalized documents (title, summary, ministers, portfolios) with versioning for soft deletes.
3. Add monitoring for indexing lag and index size, plus scripts to rebuild indexes when schema changes.

### 3. Hybrid Retrieval & Scoring
1. Build service that issues both BM25 and vector queries, normalizes scores, and computes weighted aggregate (`0.4 * bm25 + 0.6 * embedding`).
2. Implement configurable filters (date ranges, portfolios) and pagination, ensuring caching for hot queries.
3. Establish SLA budgets (<500ms P95) via load tests and tune indexes/concurrency accordingly.
4. Expose FastAPI endpoints (`/search/releases`, `/search/articles`, `/links`) and worker job that stores top related articles per release.

### 4. Link Generation & Quality Evaluation
1. Store cross-links in `links` table with similarity score, retrieval metadata, and stance placeholder (to be populated in Week 11).
2. Implement nightly evaluation job using labeled dataset to compute NDCG@3 and Recall@5, logging metrics for dashboards.
3. Provide admin tooling to review/edit generated links and blacklist low-quality sources.
4. Document retrieval configuration (weights, thresholds) for future tuning.

## Day-by-Day Timeline
- **Day 1:** Enable pgvector, design embedding schema/indexes, implement embedding worker + backfill strategy.
- **Day 2:** Run embedding backfill for releases and articles; validate cost tracking + caching.
- **Day 3:** Configure BM25/Meilisearch indexes and document ingestion pipeline.
- **Day 4:** Build hybrid retrieval service, endpoints, and link generation worker with caching.
- **Day 5:** Execute evaluation job, tune weighting to hit latency/quality targets, and summarize findings in `docs/search/week8-report.md`.

## Validation Checklist
- Embedding worker processes historical backlog without exceeding budget; retries are idempotent.
- Search endpoints return results <500ms P95 across test queries (documented via load test logs).
- Each release processed post-week8 has ≥3 related article links stored with metadata for stance classification later.
- Evaluation metrics computed nightly and surfaced in Grafana (NDCG@3 ≥0.7, Recall@5 ≥0.6 on labeled set).
- Index rebuild/runbook exists for handling schema or analyzer changes.

## Risks & Mitigations
- **High latency:** Tune pgvector parameters (lists/probes), precompute caches, and limit payload sizes.
- **Embedding cost spikes:** Batch inputs aggressively and monitor per-run spend with circuit breaker budgets.
- **Index inconsistency:** Implement transactional updates (write DB first, then enqueue search index tasks) with retries.
- **Quality drift:** Schedule periodic evaluation jobs and store historical metrics to catch regressions.

## Deliverables
- Embedding worker + pgvector indexes with cost tracking.
- Meilisearch/BM25 index configuration and ingestion scripts.
- Hybrid search APIs + link generation worker storing metadata.
- Evaluation job output + report capturing latency and quality numbers.
