Ingestion Step --- Concept & Requirements (no code)

Purpose (why this exists)

Transform Beehive RSS posts into clean, normalized, deduplicated, and verifiable records so downstream components (summarization, cross-source comparison, quizzes, dashboards, email digests) can operate on trustworthy data. The ingestion step is the single source of truth for "what was published, when, by whom, and what it says."

Outcomes (what success looks like)\
    -  Within ~1 minute of a new RSS item, there's a canonical record in storage with:\
    -  Stable ID\
    -  Core metadata (title, URL, published time, minister, portfolio)\
    -  Cleaned article text (and retained raw source)\
    -  Provenance needed for citations and verification\
    -  The record is idempotent (re-ingesting won't duplicate it) and traceable (logs + run records).\
    -  Downstream workers are signaled that a new/updated document is ready (e.g., "embed", "summarize", "compare").

Scope (what it does / does not do)

Does:\
    -  Poll one or more Beehive RSS feeds on a schedule or trigger.\
    -  Extract essential metadata from each item; optionally fetch the linked page for full text.\
    -  Clean and normalize the text to a consistent internal format.\
    -  Deduplicate using a canonical ID and upsert semantics.\
    -  Persist both raw (unaltered) and parsed (cleaned) content.\
    -  Produce run metrics and error reports.\
    -  Enqueue or mark items for the next pipeline stages.

Does not:\
    -  Generate summaries, embeddings, or comparisons (those are downstream).\
    -  Rewrite content to fit a narrative; it preserves source fidelity.\
    -  Scrape outside what the RSS item links to.

Data sources & inputs\
    -  Primary: Beehive RSS feed(s), starting with "All Releases".\
    -  Optional: Per-minister or per-portfolio RSS feeds if you later want finer granularity.\
    -  Configuration inputs:\
    -  List of feed URLs\
    -  User agent string\
    -  HTTP timeouts/retries\
    -  Backfill cursor (ingest since a date)\
    -  Rate-limit policy

Outputs & storage (conceptual model)

Each ingested item becomes a document record with:\
    -  Canonical ID: a stable identifier derived from immutable attributes (e.g., normalized title + URL). Purpose: deduping and idempotency.\
    -  Metadata: title, canonical URL, published timestamp, minister (if available), portfolio (if available), any categories/tags present.\
    -  Content:\
    -  text_raw --- what we fetched from the source (HTML or fulltext field if supplied by RSS).\
    -  text_clean --- readability-style main content extraction; normalized whitespace and quotes; minimal boilerplate.\
    -  Provenance: origin feed URL, fetch timestamp, final URL after redirects, HTTP status.\
    -  Operational flags: status (OK, PARTIAL, FAILED_FETCH, EMPTY_PARSE), attempt counts, processing notes.\
    -  Downstream state: "ready_for_embedding", "ready_for_summary", etc.

Rationale: storing both raw and clean content preserves auditability and enables re-processing if extraction improves.

Processing stages (conceptual flow)\
    1\. Schedule/Trigger\
A scheduler (cron, Actions, etc.) triggers the ingestion run at a fixed cadence (e.g., every 15--60 minutes NZ time).\
    2\. Fetch RSS\
    -  Read each configured feed URL.\
    -  Extract entries with core fields: id/guid, title, link, published date, tags/categories.\
    -  Optionally filter by a backfill cursor (ignore items older than a date).\
    3\. Canonicalization & Deduping\
    -  Compute a canonical ID from stable attributes (e.g., normalized title + normalized URL).\
    -  Maintain a per-run "seen" set to avoid double processing the same item within a run.\
    -  Query storage by canonical ID to decide insert vs update (upsert).\
    4\. Article Retrieval (if needed)\
    -  If RSS does not contain the full text, fetch the linked page.\
    -  Respect timeouts and retry policy; follow redirects; capture final URL.\
    5\. Content Extraction & Normalization\
    -  Strip scripts/styles and obvious boilerplate.\
    -  Prefer <article> or a main content container when present.\
    -  Normalize whitespace and punctuation; collapse repeated line breaks.\
    -  Keep a conservative approach --- rather miss some fluff than nuke real content.\
    -  Record quick stats (word count, language guess if trivial).\
    6\. Metadata Mapping\
    -  Derive minister and portfolio if present in tags/categories (or leave null).\
    -  Keep original categorical labels for transparency (you can refine mapping later).\
    7\. Persistence (Upsert)\
    -  If new: insert the full record.\
    -  If existing: update changed metadata and content only when better (e.g., longer/cleaner text). Never replace good content with a shorter or empty parse.\
    -  Preserve raw content alongside cleaned content.\
    8\. Downstream Signaling\
    -  Mark the document ready for embeddings/summaries/comparisons or enqueue a job reference for the next pipeline step.\
    9\. Run Accounting & Logs\
    -  Record counts: total items seen, inserted, updated, skipped, fetch failures, empty parses.\
    -  Produce structured logs with run ID and per-item trace for debugging.\
    -  Expose summary metrics for dashboards/alerts.

Idempotency & consistency guarantees\
    -  Idempotent by design: canonical ID + upsert ensures re-runs don't duplicate.\
    -  Eventual completeness: if the first attempt only stores metadata (e.g., fetch failed), later runs may enrich the record once the page becomes available.\
    -  No destructive updates: never downgrade content quality or remove retained raw data.

Performance & reliability expectations\
    -  Latency: ingest + store within ~60s of feed availability (network-dependent).\
    -  Retry policy: limited retries on transient HTTP/network errors; exponential backoff.\
    -  Throughput: Beehive posts are low volume; prioritize correctness and observability over micro-optimization.\
    -  Resource use: bounded memory; stream processing where feasible.

Error handling & partial states\
    -  FAILED_FETCH: RSS entry stored, but article retrieval failed. Downstream steps are paused until retrieval succeeds on a later run.\
    -  EMPTY_PARSE: Retrieved HTML but could not extract meaningful main content. Keep raw; allow manual or improved extractor later.\
    -  RECOVERY: Subsequent runs may upgrade PARTIAL → OK.

Governance: ethics, courtesy, compliance\
    -  Use RSS (the intended machine interface).\
    -  Identify with a polite User-Agent and modest polling cadence.\
    -  Respect robots/terms; avoid aggressive parallelism; cache where sensible.

Quality controls (before handing off downstream)\
    -  Sanity checks: title present, URL absolute, published date plausible.\
    -  Content checks: non-trivial text_clean length or justified PARTIAL flag.\
    -  Deterministic normalization (consistent across runs and machines).\
    -  Provenance completeness (we can always trace where a field came from).

Observability & metrics (what to measure)\
    -  Per run: items_total, inserted, updated, skipped_existing, fetch_failed, parsed_empty.\
    -  Latency per stage (RSS parse, fetch, extract, persist).\
    -  Percent of documents with verifier-ready content (non-empty text_clean).\
    -  Trend of failures over time (alerts if spikes occur).

Configuration (what's adjustable without code)\
    -  List of RSS feeds (start with "All Releases"; allow future minister/portfolio feeds).\
    -  Polling cadence and timezone (NZ).\
    -  HTTP timeout/retries and max concurrent fetches.\
    -  Backfill since date for historical imports.\
    -  Rate-limit knobs if adding other sources later.

Security & privacy\
    -  Only public data; no user PII.\
    -  Secrets (DB creds, API keys for any future sources) come from environment/config, not hard-coded.\
    -  Keep raw content for audit; expose full provenance in downstream UI.

Dependencies (conceptual, not implementation)\
    -  RSS parser (to interpret common feed formats).\
    -  HTML main-content extractor (readability-style) or heuristic fallbacks.\
    -  Persistent storage that supports upsert and text search (e.g., Postgres).\
    -  Optional object storage for raw HTML blobs if you separate large payloads.

Interfaces to downstream stages\
    -  Embeddings: document/chunk text available; status = ready.\
    -  Summarization: cleaned text + metadata ready; provenance links available for citation.\
    -  Cross-source search: title/clean text stored for indexing.\
    -  Digest/UI: normalized fields (title, date, minister, portfolio) available for filtering and display.

Edge cases to handle explicitly\
    -  Duplicate items across feeds (same release appearing in "All Releases" and a portfolio feed).\
    -  Corrected releases (minor title or date changes). Upsert should update metadata.\
    -  Link redirects (track final URL for consistency).\
    -  Non-article landing pages (store PARTIAL; allow human review or improved parsing).\
    -  Timezone quirks (normalize to UTC; display in NZ time later).\
    -  Temporary network issues (retry + do not block the entire run).

Acceptance criteria (definition of "done" for ingestion)\
    1\. A new release appearing in the RSS results in a single canonical record with accurate metadata and cleaned content where available.\
    2\. Re-running ingestion on the same feeds produces no duplicates and no degraded content.\
    3\. When RSS includes items older than a configured since date, they are ignored unless explicitly backfilling.\
    4\. Logs clearly show run outcomes and per-item decisions (insert/updated/skipped/failure).\
5\. A downstream flag or queue entry exists for each successful item to continue the pipeline.

Cross-source linking overview
-----------------------------

-  External news articles are fetched via `python -m beeline_ingestor.crosslink.news_ingestor`, which pulls from configurable RSS feeds (defaults: NZ Herald, RNZ National, Newsroom). Articles are stored in the `news_articles` table.
-  After each release is ingested, a lightweight cosine-similarity pass compares the release text against the latest external articles. The top matches (default 3) are stored in `release_article_links` with a similarity score and short rationale.
-  The `/releases` API now includes a `links` array per release (source, title, similarity, URL) so downstream apps can surface corroborating coverage.
-  Tune feeds or limits via `CROSSLINK_FEEDS`, `CROSSLINK_MAX_ARTICLES`, and `CROSSLINK_LINK_LIMIT` env vars. Articles older than `CROSSLINK_RETENTION_DAYS` (default 60) are pruned automatically to bound storage.
