# Week 8: Search Infrastructure – Execution Playbook

## Mission & Success Criteria
- Ship hybrid search (BM25 + embeddings) for releases/articles with pgvector + cache layers.
- Achieve <500ms query latency for top-10 results and expose search APIs/UI hooks.

## Workstreams & Detailed Tasks

### 1. Embedding Generation
1. Add embedding worker that chunks releases/articles and stores vectors in Postgres pgvector.
2. Use cost tracker + breaker for embedding API calls; batch requests for efficiency.

### 2. Hybrid Retrieval Engine
1. Configure Meilisearch or Postgres FTS for BM25-style keyword scores.
2. Combine BM25 + cosine similarity (weighted) to produce final ranking.
3. Cache common queries in Redis for 1 hour; invalidate on new releases.

### 3. Search API & UI
1. Build `/search` endpoint supporting filters (minister, portfolio, date) + pagination.
2. Add React Native search screen hooking into API and showing related articles/entities.

### 4. Performance & Quality Testing
1. Load-test 100 concurrent queries; ensure p95 <500ms.
2. Create evaluation harness using Week 4 IR dataset (NDCG@3 ≥0.7 target).

## Day-by-Day Timeline
- **Day 1:** Embedding worker + pgvector schema/migrations.
- **Day 2:** BM25 + vector retrieval implementation.
- **Day 3:** API + caching + mobile UI integration.
- **Day 4:** Load/perf testing + IR evaluation harness.
- **Day 5:** Bugfix/polish + documentation.

## Validation Checklist
- All releases/articles have embeddings stored with metadata.
- `/search` returns hybrid-ranked results in <500ms for 100-item corpus.
- Evaluation harness shows NDCG@3 ≥0.7 on labeled set.
- Mobile app search works offline-first (cached recent queries).

## Risks & Mitigations
- **Embedding cost spikes:** Batch requests, lower frequency for historical data, rely on breaker.
- **Search tuning complexity:** Start with simple weighting, iterate with evaluation dataset.
- **Cache staleness:** Use invalidation hooks when new releases/links arrive.

## Deliverables
- Embedding worker + schema.
- Hybrid search engine + API/mobile integration.
- IR evaluation report + metrics.
- Updated docs/runbooks for search operations.
