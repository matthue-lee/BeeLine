# Week 12: Entity Extraction - Detailed Implementation Plan

## Strategic Overview

Entity extraction sits at the intersection of NLP reliability and user value. The goal is to automatically identify people, organizations, policies, and locations across government releases and news articles, then create navigable entity pages that reveal relationships and trends over time.

**Key Philosophy**: Deterministic-first (regex/dictionaries) → Statistical fallback (spaCy) → No LLM (cost prohibitive for this task)

---

## Day-by-Day Implementation Breakdown

### **Day 1-2: spaCy NER Pipeline Foundation**

#### Infrastructure Setup
- Install spaCy with `en_core_web_lg` model (~800MB download)
- Create isolated Python environment to avoid dependency conflicts
- Set up processing workers that can run spaCy operations in parallel
- Configure memory limits (spaCy can use 2-4GB RAM per worker)

#### NZ-Specific Customizations
Build domain-specific entity recognition on top of spaCy:

**Minister Detection (Deterministic)**
- Compile regex patterns for official titles: "Minister of X", "Prime Minister", "Associate Minister for Y"
- Build current cabinet roster from beehive.govt.nz (scrape or manual entry)
- Track historical ministers to handle references like "former PM Ardern"
- Handle Māori diacritics properly (macrons in names like "Māori")

**Ministry/Department Detection**
- Maintain whitelist of all NZ government departments
- Include common abbreviations (MBIE, MPI, MoH, IRD, NZTA)
- Recognize Māori names (Te Puni Kōkiri, Te Whatu Ora, Oranga Tamariki)
- Catch variations ("Ministry of Business" vs "MBIE" vs "Business Ministry")

**NZ Geographic Entities**
- Load NZ gazetteer (place names, regions, cities, suburbs)
- Include Māori place names with alternative spellings
- Distinguish between "Wellington" (city) and "Wellington" (region)
- Recognize electorate names (they often appear in releases)

**Policy/Legislation Detection**
- Track bill names, act titles, policy initiatives
- Use patterns like "X Act 2024", "X Amendment Bill", "X Strategy"
- Maintain database of active consultations and initiatives
- Link short names to full legislation titles

#### Entity Validation Rules
Implement filters to reduce false positives:
- Minimum length thresholds (skip 1-2 character entities)
- Blacklist common false positives ("New Zealand", "Government", "Crown")
- Context checks (is "May" a person or a month?)
- Confidence thresholds from spaCy (ignore entities with confidence <0.6)
- Capitalization patterns (all-caps is often noise, not a name)

---

### **Day 3-4: Entity Canonicalization (Name Matching)**

This is the hardest part—linking "Luxon", "Christopher Luxon", and "PM Luxon" to one canonical entity.

#### Canonical Entity Strategy

**Build Authority Records**
Create a `canonical_entities` reference table:
- Authoritative name (e.g., "Christopher Luxon")
- Entity type (PERSON, ORG, GPE, POLICY)
- Known aliases (["Luxon", "PM Luxon", "Chris Luxon"])
- Metadata (party affiliation, portfolio, title)
- Date ranges (tenure as PM, portfolio assignments)

**Multi-Stage Matching Pipeline**

**Stage 1: Exact Match**
- Check detected entity against canonical names and aliases
- Fastest path, handles 70-80% of cases
- Use hash lookups for O(1) performance

**Stage 2: Fuzzy Matching**
For entities not found in Stage 1:
- String similarity metrics: Levenshtein distance, Jaro-Winkler
- Account for common misspellings, OCR errors
- Handle "MacDonald" vs "McDonald", "O'Brien" vs "OBrien"
- Threshold: >0.85 similarity = match candidate

**Stage 3: Contextual Disambiguation**
For ambiguous matches (e.g., "David Clark" - which one?):
- Check surrounding context (portfolio, ministry, date)
- If release mentions "Health" near "Clark" → health minister David Clark
- If release is from 2018-2020 → not current David Clark
- Use co-occurrence patterns from training data

**Stage 4: Human-in-the-Loop**
For unresolved entities:
- Create temporary entity with `canonical_id = NULL`
- Flag for manual review in admin panel
- Show suggested matches based on fuzzy similarity
- Admin decision creates alias rule for future auto-matching

#### Alias Learning System
Automatically grow alias database over time:
- When admin confirms "PM Luxon" → "Christopher Luxon", store as alias
- Track alias usage frequency (common aliases vs rare typos)
- Periodically review low-confidence auto-matches
- Export alias rules as version-controlled config (rollback capability)

#### Handling Name Changes and Transitions
- Track entity relationships: "Hipkins succeeded Ardern as PM"
- Store tenure periods for roles (Luxon: PM from 2023-11-27)
- When processing historical documents, match entities to their context-appropriate canonical form
- Flag entities that changed names (organization rebrandings, married names)

---

### **Day 5: Entity Detail Pages Architecture**

#### Data Requirements for Entity Pages

**Core Entity Information**
- Canonical name, type, current role/status
- Biography summary (for people) or description (for orgs)
- Photo/logo (optional, sourced externally or manually added)
- Social media handles, official websites
- Related entities (colleagues, parent organizations)

**Mentions Timeline**
Query design for efficient retrieval:
- Index: `mentions(entity_id, created_at DESC)`
- Paginated queries: "Show 20 most recent mentions, load more on scroll"
- Filter by source type (releases only, articles only, both)
- Filter by date range (last 30 days, custom range)

**Aggregated Statistics**
Pre-compute for performance:
- Total mentions across all documents
- Mentions per month (trend data for charts)
- Most mentioned with (co-occurrence leaders)
- Sentiment trend (if implementing sentiment analysis)
- Portfolio/topic association strength

**Related Content Sections**
- "Latest Releases Featuring This Entity" (top 5, link to full list)
- "Recent News Coverage" (top 5 articles)
- "Frequently Mentioned With" (co-occurrence network)
- "Activity Timeline" (chart showing mention frequency over time)

#### Page Performance Optimization

**Caching Strategy**
- Cache entity summary data (name, stats, bio) for 24 hours
- Cache mention timelines for 1 hour (stale data acceptable)
- Invalidate cache when new mentions are added
- Use Redis with key pattern: `entity:{id}:summary`, `entity:{id}:mentions:page:{n}`

**Lazy Loading**
- Load "above the fold" content immediately (name, photo, latest 5 mentions)
- Lazy load co-occurrence graph, timeline chart, full mention list
- Use skeleton screens while data loads
- Infinite scroll for mention pagination (avoid "load more" buttons)

**Database Query Optimization**
- Materialize aggregated stats in `entity_statistics` table (updated nightly)
- Use covering indexes for common queries
- Avoid N+1 queries when loading mentions with release/article metadata
- Implement cursor-based pagination (more efficient than offset/limit)

---

### **Day 6-7: Co-occurrence Tracking**

#### Co-occurrence Definition
Two entities co-occur if they appear in the same document within reasonable proximity (same paragraph, within 500 characters, or both mentioned anywhere).

**Three Levels of Co-occurrence**

**Level 1: Document-Level** (simplest)
- Entities appear anywhere in the same release or article
- Most inclusive, captures all relationships
- Good for: "Who works in the same government areas?"

**Level 2: Paragraph-Level** (moderate)
- Entities appear in the same paragraph
- Better signal of direct relationship
- Good for: "Who is directly quoted together?"

**Level 3: Sentence-Level** (strongest)
- Entities appear in the same sentence
- Highest confidence of relationship
- Good for: "Who explicitly interacts with whom?"

**Implementation Recommendation**: Start with document-level, add paragraph/sentence-level in post-launch optimization.

#### Efficient Co-occurrence Computation

**Batch Processing Approach**
Don't compute on-the-fly during entity extraction:
1. Extract all entities from document → store mentions
2. After all extractions complete, run co-occurrence job
3. For each document, generate entity pairs
4. Upsert into `entity_cooccurrences` table (increment count if exists)

**Optimization for Large Documents**
- If document has 50 entities, that's 1,225 potential pairs (n² problem)
- Limit to top 20 most prominent entities per document (mentioned most frequently)
- OR: Only compute co-occurrence for entities mentioned ≥2 times in document

**Incremental Updates**
- When new document arrives, only compute co-occurrences for entities in that document
- Update existing co-occurrence counts (add 1 to existing pairs)
- Track `last_seen` timestamp for temporal analysis
- Store `source_documents` array to enable "view co-occurrence context" feature

#### Relationship Type Classification

Beyond simple co-occurrence counts, classify relationship types:

**Deterministic Relationships**
- Both entities are ministers → "colleagues"
- Entity A is a ministry, Entity B is a minister → "portfolio_assignment"
- Entity A is a policy, Entity B is a minister → "policy_sponsor"
- Entity A is organization, Entity B is person → check if "CEO", "chair", "director" appears nearby

**Statistical Patterns**
- Frequently co-occur in positive context → "allies"
- Frequently co-occur with disagreement language → "opposition"
- One consistently quoted about the other → "subject_expert"

**User-Facing Labels**
- Display as: "Often mentioned with", "Works in same portfolio", "Quoted together"
- Avoid speculative labels like "supports" or "opposes" without high confidence

#### Co-occurrence Visualization Considerations

**Entity Relationship Graph**
- Nodes = entities, edges = co-occurrence count (edge weight)
- Filter to top N relationships (don't show weak connections)
- Use force-directed layout for clear visualization
- Color-code by entity type (blue for people, green for orgs, etc.)
- Make clickable (click entity node → navigate to that entity page)

**Performance Concerns**
- Don't render 500-node graphs (browser will crash)
- Pre-compute graph layout on server (don't compute in browser)
- Offer zoom levels: "Immediate network" (1-hop), "Extended network" (2-hop)
- Export as static SVG or pre-rendered image for fast loading

---

## Database Schema Deep Dive

### **entities Table**
```
Columns:
- id (PK)
- canonical_name (unique, indexed)
- entity_type (indexed: PERSON, ORG, GPE, POLICY, MINISTRY)
- aliases (array, GIN indexed for fast lookup)
- metadata (JSONB: {title, party, portfolio, tenure_start, tenure_end})
- first_seen, last_seen (track activity range)
- mention_count (denormalized for sorting/filtering)

Indexes:
- B-tree on canonical_name (exact lookups)
- GIN on aliases (array containment)
- B-tree on entity_type (filtering by type)
- Trigram GIN for fuzzy search
```

### **mentions Table**
```
Columns:
- id (PK)
- entity_id (FK to entities, indexed)
- source_type ('release' or 'article')
- source_id (FK to releases/articles)
- context (text snippet, 200 chars around entity)
- position (character offset in document)
- confidence (spaCy confidence score)
- detected_as (actual text recognized, for debugging)

Indexes:
- Composite: (entity_id, created_at DESC) for timeline queries
- Composite: (source_type, source_id) for reverse lookups
- B-tree on confidence (filter low-confidence mentions)

Partitioning Strategy (future):
- Partition by created_at (monthly partitions)
- Enables fast purging of old data
- Improves query performance on recent mentions
```

### **entity_cooccurrences Table**
```
Columns:
- id (PK)
- entity_a_id, entity_b_id (FKs, ensure entity_a_id < entity_b_id to avoid duplicates)
- cooccurrence_count
- source_documents (array: ["release:123", "article:456"])
- relationship_type (nullable: 'colleagues', 'portfolio_assignment', etc.)
- last_seen

Indexes:
- Composite unique: (entity_a_id, entity_b_id)
- B-tree on cooccurrence_count DESC (top relationships)
- GIN on source_documents (find all co-occurrences in specific document)

Constraints:
- CHECK(entity_a_id < entity_b_id) to prevent (A,B) and (B,A) duplicates
```

### **entity_statistics Table** (Materialized View)
```
Refreshed nightly via cron job:

Columns:
- entity_id (PK, FK to entities)
- mentions_last_7_days
- mentions_last_30_days
- mentions_all_time
- top_cooccurrences (pre-computed JSON: [{entity_id, count}, ...])
- mentions_by_month (JSON: {"2024-01": 15, "2024-02": 23})
- avg_mentions_per_week

Usage:
- Entity list sorting: "Most active entities this month"
- Entity page "Quick Stats" section
- Avoids expensive real-time aggregations
```

---

## Worker Architecture

### **Entity Extraction Worker**

**Job Queue Design**
```
Job Type: 'extract_entities'
Priority: Normal (after summarization, before cross-linking)
Payload: {source_type, source_id, text}
```

**Processing Flow**
1. Receive job from queue
2. Load text from database (or accept in payload if small)
3. Run deterministic patterns (ministers, ministries, policies)
4. Run spaCy NER on remaining text
5. Validate and filter entities
6. Canonicalize each entity (lookup + fuzzy match)
7. Batch insert mentions to database
8. Enqueue co-occurrence job (separate worker)
9. Update entity.last_seen timestamps
10. Log metrics (entities found, processing time)

**Error Handling**
- If spaCy crashes (rare, but happens with malformed Unicode): fall back to deterministic-only
- If canonicalization fails: store with `canonical_id = NULL`, flag for review
- If database write fails: retry with exponential backoff (3 attempts)
- If job fails 3x: move to dead letter queue, alert admin

**Concurrency & Resource Management**
- Limit to 2-3 concurrent workers (spaCy is memory-hungry)
- Set worker timeout: 60 seconds per document
- Use worker health checks (restart if memory >4GB)
- Process small documents (<5000 chars) faster by batching

### **Co-occurrence Worker**

**Job Queue Design**
```
Job Type: 'compute_cooccurrences'
Priority: Low (not time-sensitive)
Payload: {source_type, source_id}
Triggered after: Entity extraction completes
```

**Processing Flow**
1. Fetch all mentions for this document
2. Generate entity pairs (limit to top 20 entities if >20 found)
3. For each pair:
   - Check if co-occurrence record exists
   - If exists: increment count, append source_id, update last_seen
   - If new: insert record
4. Update entity statistics (if large batch, defer to nightly job)

**Optimization Tricks**
- Use UPSERT (INSERT ... ON CONFLICT UPDATE) for atomic updates
- Batch all upserts in single transaction
- Skip pairs where entities are same type and very common (e.g., "New Zealand" + "Government")
- Cache entity type lookups to avoid repeated queries

---

## Security & Privacy Considerations

### **PII Handling**
Government releases may mention private individuals (submitters, complainants, victims):
- Flag entities with low mention counts (<3) for manual review before publishing
- Redact entities marked as "PII" from public entity pages
- Store full data in database, filter at query time
- Admin override to mark entities as "public figure" vs "private individual"

### **Defamation Risk**
Co-occurrence data could imply false relationships:
- Add disclaimer: "Co-occurrence does not imply endorsement or relationship"
- Avoid labels like "allies" or "opposes" without explicit evidence
- Provide context links: "View documents where mentioned together"
- Allow users to report inappropriate entity pages

### **Data Retention**
- Keep mention records indefinitely (needed for historical analysis)
- Archive old co-occurrence records (>2 years) to cheaper storage
- GDPR compliance (if applicable): provide entity deletion mechanism
- Log all entity edits for audit trail

---

## Rate Limiting & Efficiency

### **Processing Rate Limits**

**spaCy Processing**
- spaCy is CPU-bound, not API-limited
- Limit: process 100 documents/hour per worker
- Use queue backlog monitoring: if >200 docs queued, scale up workers
- Prioritize new releases over backfill (queue priority system)

**Database Write Limits**
- Batch insert mentions (100-500 per transaction)
- Use bulk upsert for co-occurrences (1000+ per transaction)
- Avoid individual INSERT per mention (kills performance)
- Connection pool: 10-20 connections max

**Memory Management**
- Unload spaCy model between batches if processing large docs
- Use generator patterns for large result sets
- Monitor worker RSS memory, restart at 4GB threshold
- Implement circuit breaker: if worker crashes 3x in 10min, pause queue

### **Query Optimization for Entity Pages**

**Caching Strategy**
- Cache entity profile (name, stats, bio): 24 hours, invalidate on edit
- Cache mention list per page: 1 hour, invalidate on new mention
- Cache co-occurrence graph: 6 hours (expensive to compute)
- Use Redis cache-aside pattern with TTL

**Database Query Performance**
- Covering indexes for common queries (avoid table lookups)
- Use EXPLAIN ANALYZE to identify slow queries
- Consider read replicas for entity page queries (high read load)
- Implement query result pagination (cursor-based, not offset)

**Front-End Optimization**
- Server-side render entity pages for SEO and speed
- Lazy load graphs, timelines, full mention lists
- Use CDN for static assets (entity photos, logos)
- Implement optimistic UI updates (edit entity → update UI immediately, sync async)

---

## Quality Assurance & Validation

### **Entity Extraction Accuracy**

**Ground Truth Dataset**
Create labeled test set (Week 4 deliverable mentions 20 releases):
- Manually annotate entities in 20 diverse releases
- Include edge cases: Māori names, abbreviations, ambiguous entities
- Tag with canonical entity IDs

**Automated Evaluation**
Run nightly:
- Precision: % of extracted entities that are correct
- Recall: % of actual entities that were found
- F1 score: harmonic mean of precision/recall
- Target: F1 > 0.85 for PERSON, > 0.80 for ORG

**Error Analysis**
Common failure modes to monitor:
- False negatives: missed entities (especially Māori names)
- False positives: noise words detected as entities
- Canonicalization errors: "Luxon" linked to wrong person
- Type errors: person detected as organization

### **Canonicalization Accuracy**

**Test Canonical Matching**
- Create test cases with known aliases: "PM Ardern" → "Jacinda Ardern"
- Measure: % of aliases correctly resolved
- Target: >95% accuracy on common entities, >80% on rare entities

**Review Queue**
- All entities with `canonical_id = NULL` go to manual review
- Admin resolves: create new entity, or link to existing
- Track review queue size (if >100, improve auto-matching rules)

### **Co-occurrence Quality**

**Sanity Checks**
- Most common co-occurrences should make sense (PM + Finance Minister, etc.)
- Flag suspicious co-occurrences (entities from unrelated domains)
- Monitor co-occurrence count distribution (spike detection)

**User Feedback Loop**
- Allow users to report incorrect relationships
- Track report frequency per entity pair
- If entity pair has >3 reports, flag for review

---

## User Experience Design

### **Entity Discovery**

**Search & Browse**
- Entity search bar: autocomplete with fuzzy matching
- Browse by type: "All Ministers", "All Ministries", "All Policies"
- Filter by activity: "Most mentioned this week", "Trending entities"
- Sort by: mention count, recency, alphabetical

**Smart Suggestions**
- On release detail page: highlight detected entities, link to entity pages
- "Related entities you might be interested in" (based on co-occurrence)
- "Follow this entity" → get notifications when mentioned in new releases

### **Entity Page Layout**

**Hero Section**
- Large entity name, photo/logo
- Key metadata (title, portfolio, party, tenure dates)
- Quick stats: total mentions, mentions this month, trend indicator (↑↓)

**Activity Timeline**
- Chart showing mentions per month over time
- Clickable bars: filter mention list by date range
- Overlay major events (elections, portfolio changes)

**Mentions Section**
- Paginated list of mentions
- Each item: snippet with entity highlighted, source title, date
- Filter controls: source type, date range, keyword search
- Export button: download mentions as CSV

**Relationship Network**
- Visual graph of co-occurrences (top 10-20 relationships)
- Hoverable nodes: show entity name, mention count
- Clickable edges: show shared documents

**Related Content**
- "Latest releases featuring [entity]" (5 items, link to full list)
- "Recent news coverage" (5 articles, link to full list)
- "Frequently mentioned with" (top 5 co-occurring entities)

### **Mobile Considerations**
- Collapsible sections (expand "Relationship Network" on demand)
- Infinite scroll for mentions (avoid pagination buttons)
- Touch-friendly graph (pan, pinch-to-zoom)
- Fast loading: prioritize hero section, lazy load everything else

---

## Admin Tools & Debugging

### **Entity Management Dashboard**

**Entity Review Queue**
- List all entities with `canonical_id = NULL`
- Show detected text, document context, suggested matches
- One-click actions: "Create new entity", "Link to existing entity"
- Bulk operations: "Mark all as noise", "Auto-link high-confidence matches"

**Canonical Entity Editor**
- Edit entity name, type, metadata
- Add/remove aliases (with approval workflow)
- Merge duplicate entities (combine mention histories)
- Split incorrectly merged entities (undo bad canonicalization)

**Extraction Debugging**
- View extraction results for specific document
- Highlight detected entities in original text
- Show confidence scores, detected type, canonical match
- Re-run extraction with different settings (test new patterns)

### **Quality Monitoring**

**Dashboard Metrics**
- Entities extracted per day (trend chart)
- Extraction success rate (% of jobs completed without errors)
- Canonicalization rate (% of entities matched to canonical IDs)
- Review queue size (alert if >100 pending reviews)
- Top entities by mention count (sanity check for noise)

**Alerts**
- Spike in entity extractions (possible spam or bad data)
- Spike in failed canonicalizations (pattern file corrupted?)
- Slow extraction times (spaCy worker overloaded?)
- High memory usage (restart worker before OOM crash)

---

## Testing Strategy

### **Unit Tests**
- Entity validation logic (is_valid_entity function)
- Canonical matching (exact, fuzzy, contextual)
- Co-occurrence pair generation
- Alias normalization (handle diacritics, capitalization)

### **Integration Tests**
- End-to-end: ingest document → extract entities → store mentions → compute co-occurrences
- Database constraints: ensure no duplicate entity pairs
- Cache invalidation: update entity → cache cleared
- Queue flow: extraction job → co-occurrence job triggered

### **Performance Tests**
- Load test: process 100 documents simultaneously
- Query performance: entity page with 10,000 mentions loads <2s
- Memory leak detection: run extraction worker for 1000 docs, check RSS
- Database scalability: insert 100k mentions, measure query time degradation

### **Accuracy Tests**
- Run extraction on labeled test set (20 docs)
- Measure precision, recall, F1 for each entity type
- Compare to baseline (previous version)
- Regression detection: alert if accuracy drops >5%

---

## Deployment Checklist

### **Pre-Deployment**
- [ ] spaCy model downloaded and verified (en_core_web_lg)
- [ ] Database schema migrated (entities, mentions, co-occurrences tables)
- [ ] Indexes created and analyzed
- [ ] Worker configured with resource limits (memory, timeout)
- [ ] Caching layer (Redis) tested and connected
- [ ] Monitoring dashboards created (extraction metrics, queue depth)

### **Deployment Steps**
1. Deploy database schema changes (run migrations)
2. Deploy entity extraction worker (start with 1 worker)
3. Deploy co-occurrence worker (separate queue)
4. Deploy entity page API endpoints
5. Deploy admin dashboard
6. Backfill: enqueue extraction jobs for existing releases (low priority)
7. Monitor extraction queue (should drain at ~100 docs/hour)

### **Post-Deployment Validation**
- [ ] Extraction worker processing jobs successfully
- [ ] Mentions appearing in database
- [ ] Entity pages rendering correctly
- [ ] Co-occurrence graph displays
- [ ] Admin review queue functional
- [ ] No memory leaks after 24 hours
- [ ] Accuracy metrics meet targets (F1 > 0.85)

### **Rollback Plan**
If extraction causes critical issues:
1. Pause entity extraction queue
2. Gracefully drain current jobs (finish in-progress work)
3. Revert code deployment
4. Investigate errors in logs
5. Fix and redeploy
6. Resume queue processing

---

## Long-Term Optimization Ideas

### **Post-Launch Enhancements**

**Temporal Entity Linking**
- Track entity role changes over time
- "David Clark" in 2019 → Health Minister
- "David Clark" in 2024 → different person or no longer minister
- Use tenure metadata to disambiguate

**Entity Sentiment Analysis**
- Analyze sentiment of mentions (positive, neutral, negative)
- Show sentiment trend on entity page
- Alert on sudden sentiment shifts (crisis detection)

**Entity Salience Scoring**
- Not all mentions are equal (headline vs footnote)
- Weight mentions by position in document (earlier = more salient)
- Weight by document importance (major policy vs minor update)
- Use salience for "trending entities" detection

**Cross-Language Support**
- Detect Māori text blocks
- Use Māori NER models (if available)
- Link Māori and English entity names (Te Whatu Ora ↔ Health NZ)

**Automated Fact-Checking**
- Cross-reference entity claims across sources
- Flag contradictions (Minister X says Y in release, says Z in news)
- Generate "claim consistency scores" for entities

---

## Success Criteria for Week 12

### **Deliverable Checklist**
- [ ] spaCy pipeline extracts entities from releases and articles
- [ ] Entity canonicalization matches >90% of common entities correctly
- [ ] Entity detail pages display mentions, stats, and co-occurrence graph
- [ ] Co-occurrence tracking functional (pair generation, storage, retrieval)
- [ ] Entity pages load in <2 seconds with 100+ mentions
- [ ] Admin can review and resolve unmatched entities
- [ ] Extraction metrics dashboard shows success rate, throughput
- [ ] Backfill job processed 100+ historical releases

### **Quality Gates**
- Precision > 0.85 (few false positives)
- Recall > 0.80 (few missed entities)
- Canonicalization accuracy > 90%
- Entity page query time < 2 seconds (P95)
- Zero critical errors in 24-hour test run

### **User Value Validation**
- Can navigate from release → entity page → related releases
- Entity pages reveal non-obvious relationships (via co-occurrence)
- Trending entities widget shows meaningful, timely results
- Search returns relevant entities quickly (<500ms)

---

This plan balances ambition with pragmatism—start with deterministic extraction and spaCy, then iterate based on real-world results. The key is building strong infrastructure (good schema, efficient workers, clear monitoring) that can support sophisticated features later.