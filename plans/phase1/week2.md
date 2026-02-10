# Week 2: Ingestion Pipeline – Execution Playbook

## Mission & Success Criteria
- Build robust RSS → cleaned release ingestion covering error handling, rate limiting, and deduplication via SHA256 IDs.
- Process at least 100 historical releases end-to-end (fetch, parse, clean, store) to validate throughput.
- Produce inspection endpoints/CLI commands to verify stored releases quickly.

## Workstreams & Detailed Tasks

### 1. RSS Fetching & Rate Limiting
1. Expand `FeedConfig` to handle multiple feeds with per-feed backoff timers.
2. Implement `FeedClient` retry strategy (exponential backoff, jitter, max attempts configurable via env).
3. Respect `robots.txt` and add custom UA string (already in config) with tests verifying headers.
4. Instrument fetch durations and HTTP status counts for monitoring.

### 2. HTML Retrieval & Parsing
1. Build `ArticleFetcher` that follows redirects and detects anti-bot challenges so feeds can be skipped without attempting bypasses.
2. Integrate Readability/BeautifulSoup cleaning to strip navigation cruft and inline styles.
3. Capture provenance metadata (final URL, status, content length) for each fetch attempt.

### 3. Cleaning, Dedupe & Persistence
1. Normalize whitespace, decode HTML entities, remove footers, build `ContentCleaner` heuristics for Beehive structure.
2. Generate stable SHA256 IDs using URL + published timestamp fallback; guard against duplicates via DB constraints.
3. Enforce `min_content_length` before marking documents as `OK`; otherwise use `PARTIAL`/`FAILED_FETCH` statuses.
4. Record word counts, categories, minister/portfolio metadata when available.

### 4. Backfill & Verification Tooling
1. Extend CLI (`beeline_ingestor.cli`) with `--since` and `--limit` plus a `backfill` subcommand for historical runs.
2. Provide `scripts/backfill_releases.py` that iterates by month windows to avoid feed pagination limits.
3. Add `/releases` inspection endpoint (already scaffolded) with filters for minister and date to spot-check data.
4. Write unit/integration tests covering fetcher error paths, dedupe, and storage logic using SQLite test DB.

## Day-by-Day Timeline
- **Day 1:** Harden RSS fetcher (rate limiting, retries), add tests, instrument metrics.
- **Day 2:** Implement HTML fetch + cleaner improvements, provenance metadata.
- **Day 3:** Wire persistence updates (dedupe, statuses, SHA IDs) and verify DB entries.
- **Day 4:** Build backfill tooling + CLI enhancements; run initial historical import.
- **Day 5:** Process ≥100 releases, document runbooks, fix defects discovered during backfill.

## Validation Checklist
- `python -m beeline_ingestor --since <date>` ingests without unhandled exceptions and logs status counts.
- Database shows ≥100 `releases` with `status = 'OK'` or `PARTIAL` and realistic metadata.
- Inspection endpoint/CLI returns JSON list within SLA (<2s for 100 releases).
- Tests cover fetch failure/retry, dedupe, cleaning (CI green).

## Risks & Mitigations
- **Feed throttling / bans:** Implement `Retry-After` respect, configurable sleep, and feed-level state persisted to disk.
- **HTML edge cases:** Keep fallback to RSS summary when cleaning fails; log for manual review.
- **Backfill overload:** Batch by month, insert small sleeps between requests, monitor memory.
- **Data drift:** Store raw + cleaned text for auditing and maintain ability to re-clean later weeks.

## Deliverables
- Enhanced RSS/HTTP clients with retry + metrics.
- Content cleaner utilities and dedupe hashing logic.
- Backfill script + documented run instructions.
- Evidence of 100 historical releases ingested (screenshot/log snippet in `docs/week2-report.md`).
