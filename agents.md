# NZ Beehive Policy Brief -- Strategic Plan (16 Weeks)
============================================================

> **Goal:** Turn Beehive.govt.nz releases into *actionable understanding* with a production-quality pipeline, rigorous evaluation, and a clean UX. This plan provides strategic direction and architectural guidance for implementation teams.

---

## Executive Summary & Changes from V1

### Critical Fixes to Original Plan

**Timeline Extended: 8 → 16 Weeks**
- Original timeline was unrealistic for single developer (would require expert team of 3-4)
- New timeline accounts for integration complexity, debugging, and iteration
- Built-in buffer for unexpected issues and learning curve

**Cost Management Added**
- Monthly budget projection: $200-600 at steady state
- Circuit breakers to prevent runaway API costs
- Template-based fallbacks when budget exceeded
- Real-time cost monitoring and alerts

**Data Model Enhanced**
- Added 10+ tables for production needs (users, cost tracking, failed jobs, audit logs)
- Versioning and soft deletes for data integrity
- Proper indexing strategy for performance
- Separate tracking for system health vs business logic

**Operational Excellence**
- Monitoring-first approach (observability from day 1)
- Queue-based architecture for reliability
- Graceful degradation strategies
- Clear runbooks and maintenance procedures

**Sustainable Design**
- Prompt version control and A/B testing capability
- Manual override paths for AI failures
- Clear separation between fast/slow operations
- Cost-aware scheduling and throttling

---

## North-Star & Success Criteria

### Vision
Create a **reliable, cost-effective system** that transforms dense government releases into scannable, verified briefs with cross-source context—demonstrating production AI engineering best practices.

### Success Metrics (Measurable)

**Technical Performance**
- ✅ 60-second SLA: RSS appearance → stored, summarized, visible
- ✅ 99% uptime for API and job processing
- ✅ <1% job failure rate with automatic recovery
- ✅ Page load time <2s for list view (100 releases)

**AI Quality**
- ✅ ≥90% of claims traceable to exact source sentences
- ✅ NDCG@3 ≥ 0.7 for cross-source retrieval
- ✅ ROUGE-L ≥ 0.40 vs human-written summaries
- ✅ Verification pass rate ≥85%

**Cost Efficiency**
- ✅ Monthly LLM costs <$600 (avg $20/day)
- ✅ Automatic fallback when hourly budget exceeded
- ✅ <5% of summaries generated via fallback templates

**User Value**
- ✅ Daily email delivered by 8:30 AM NZDT, <5% bounce rate
- ✅ Each release shows 3-5 relevant news articles
- ✅ Average reading time saved: 15 min/release → 2 min/brief

---

## System Architecture & Design Principles

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         SCHEDULER LAYER                          │
│  (GitHub Actions cron + Manual Triggers + Webhook Endpoints)     │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├──[hourly]──→ Fetch RSS feeds
             ├──[daily]───→ Generate email digest
             └──[nightly]─→ Run evaluation suite
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    QUEUE LAYER (Redis/BullMQ)                    │
│  Job Types: ingest → summarize → verify → embed → link          │
│  Priorities: High (new) > Normal (backfill) > Low (reprocess)   │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├──[fast]────→ Ingest Worker (parsing, cleaning)
             ├──[slow]────→ LLM Worker (summarize, verify) ← cost controls
             ├──[medium]──→ Search Worker (cross-linking)
             └──[fast]────→ Extract Worker (spaCy NER)
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (Postgres)                       │
│  Tables: releases, summaries, articles, links, entities,        │
│          users, jobs, llm_calls, daily_costs, content_flags     │
│  Caching: Redis (summaries 24h, embeddings ∞, search 1h)       │
│  Storage: S3/MinIO (raw HTML, evaluation datasets)              │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├──→ React Native App (list, search, compare, entities)
             ├──→ Email Service (daily digest, alerts)
             ├──→ Metrics API (Prometheus exports)
             └──→ Admin Panel (job control, prompt testing, flags)
```

### Core Design Principles

**1. Separation of Concerns**
- **Deterministic operations** (parse, clean, dedupe) → Fast workers, no LLM
- **AI operations** (summarize, verify) → Slow workers, cost-controlled, with fallbacks
- **Search operations** (BM25, embeddings) → Hybrid approach, cached aggressively

**2. Reliability Through Queues**
- Decouples ingestion from processing (system can ingest even if LLM is down)
- Retry logic with exponential backoff
- Dead letter queues for manual intervention
- Job dependencies (verify waits for summarize)

**3. Cost-Aware Architecture**
- All LLM calls go through circuit breaker
- Automatic fallback to template-based summaries
- Rate limiting at multiple levels (hourly, daily, monthly)
- Cost tracking per operation for optimization

**4. Graceful Degradation**
- When LLM unavailable → extractive summarization
- When News API down → cache-only cross-linking
- When verification fails → flag for manual review
- System continues operating with reduced features

**5. Observable by Default**
- Every job logs start/end times
- All LLM calls tracked (tokens, cost, latency)
- Metrics exposed for Prometheus scraping
- Structured JSON logs for easy parsing

---

## Data Model Strategy

### Core Entity Relationships

```
CONTENT FLOW:
Release (1) ──→ (1) Summary ──→ (N) Claims ──→ Verification
   │                                              
   ├──→ (N) Embeddings (chunks)
   ├──→ (N) Mentions ──→ (N) Entities
   └──→ (N) Links ──→ (N) Articles

USER FLOW:
User (1) ──→ (N) DigestSends ──→ (N) Releases included
   │
   └──→ (1) Preferences (portfolios, ministers of interest)

SYSTEM FLOW:
JobRun (1) ──→ (N) LLMCalls (cost tracking)
   │
   └──→ (0..1) FailedJob (if failed, for retry)

QUALITY CONTROL:
Summary/Release (1) ──→ (N) ContentFlags ──→ Manual Review
```

### Key Tables & Responsibilities

**Content Tables**
- `releases` - Core government releases (with versioning, soft deletes)
- `articles` - External news articles for cross-referencing
- `summaries` - LLM-generated summaries (linked to prompt version)
- `links` - Cross-source connections (with similarity scores, stance)
- `entities` - Named entities (people, orgs, policies)
- `mentions` - Entity occurrences in documents

**User Tables**
- `users` - Email, preferences, subscription status
- `digest_sends` - Tracking what was sent when (for engagement metrics)

**Operational Tables**
- `job_runs` - All job executions (status, duration, params, results)
- `failed_jobs` - Jobs that failed (for retry scheduling)
- `llm_calls` - Every LLM API call (tokens, cost, latency, purpose)
- `daily_costs` - Rollup table for fast dashboard queries

**Quality Tables**
- `content_flags` - Issues detected by system or reported by users
- `prompt_templates` - Versioned prompts with A/B testing capability

### Indexing Strategy

**Performance-Critical Indexes**
- `releases(published_at DESC)` - Timeline queries
- `releases(minister, portfolio)` - Filter queries
- GIN index on `to_tsvector(text_clean)` - Full-text search
- HNSW index on `embeddings` - Vector similarity search

**Operational Indexes**
- `job_runs(status, name)` - Dashboard queries
- `llm_calls(created_at)` - Cost tracking
- `failed_jobs(next_retry_at)` - Retry scheduler

**Data Integrity**
- Soft deletes via `deleted_at` timestamp
- Versioning via `version` integer + `superseded_by` FK
- Audit trail via `created_at`, `updated_at` on all tables

---

## Cost Model & Controls

### Monthly Budget Projection

**Baseline Scenario** (50 releases/day)

| Component | Daily Cost | Monthly Cost |
|-----------|------------|--------------|
| Summarization (GPT-4o-mini) | $0.30 | $9.00 |
| Verification (GPT-4o-mini) | $0.12 | $3.60 |
| Embeddings (text-embedding-3-small) | $0.002 | $0.06 |
| News API (flat fee) | - | $200.00 |
| Infrastructure (Fly.io) | $0.65 | $19.50 |
| **Total** | **$1.07** | **$232.16** |

**High-Traffic Scenario** (150 releases/day + user queries)

| Component | Monthly Cost |
|-----------|--------------|
| LLM operations | $37.80 |
| News API | $200.00 |
| Infrastructure | $19.50 |
| **Total** | **$257.30** |

### Cost Control Mechanisms

**Circuit Breaker System**
- Track spend in Redis with sliding windows (hourly, daily, monthly)
- When 90% of limit reached → open circuit for that operation
- Automatic fallback to template-based methods
- Circuit auto-resets after 30 minutes
- Admin override capability for urgent processing

**Fallback Strategies**
- Summarization → TF-IDF extractive summary (no LLM)
- Verification → skip, flag for manual review
- Cross-linking → cache-only, no new API calls
- Entity extraction → regex-based (ministers, portfolios only)

**Rate Limiting**
- OpenAI: 500 requests/minute (tier 2)
- News API: 100 requests/day (free tier)
- Embeddings: batched to 500 texts/request
- All wrapped in Bottleneck rate limiters

**Monitoring & Alerts**
- Real-time Grafana gauge showing hourly spend vs limit
- Slack/email alerts at 80%, 90%, 100% thresholds
- Weekly cost reports by operation type
- Monthly projections based on 7-day rolling average

---

## AI Pipeline Strategy

### Prompt Engineering Approach

**Structured Outputs**
- All LLM responses use JSON mode with Zod schemas
- Strict validation before storage
- Auto-rejection of malformed outputs

**Version Control**
- Prompts stored in DB with semantic versioning (v1.0, v2.1)
- Each summary links to prompt version used
- A/B testing capability (route 10% to new prompt, compare metrics)
- Easy rollback if quality degrades

**Quality Guardrails**
- Pre-filters: Check input length, content type
- Post-filters: Detect speculation, opinion language, vague quantifiers
- Auto-corrections: Remove hedging, fix capitalization
- Manual review: Low-confidence outputs flagged

### Summarization Pipeline

**Step 1: Generate Draft**
- Input: cleaned release text + metadata
- Model: GPT-4o-mini (cost-effective, fast)
- Temperature: 0.3 (consistent outputs)
- Max tokens: 500 (brief summaries only)
- Output: {short, why_it_matters, claims[], citations[]}

**Step 2: Verify Claims**
- For each claim, retrieve supporting sentences from source
- Use QA-style prompt: "Which sentence supports this claim?"
- If no support found → drop claim or flag
- Track verification score (% of claims supported)

**Step 3: Quality Check**
- Run content filters (no speculation, citations present)
- If quality issues → flag for review, don't block publication
- Store both raw and filtered versions

**Step 4: Store & Cache**
- Save to DB with full provenance (model, prompt version, cost)
- Cache in Redis for 24 hours
- Invalidate cache if release is updated

### Cross-Source Linking Strategy

**Hybrid Search**
- BM25 (keyword matching) for exact phrase matches
- Embeddings (semantic similarity) for conceptual matches
- Combine scores: `final_score = 0.4 * bm25 + 0.6 * embedding`

**Two-Stage Retrieval**
1. **Fast pass**: Search local articles DB (cached results, <100ms)
2. **Slow pass**: Query News API if <3 results found (rate-limited)

**Stance Detection**
- Compare release summary to article text
- Categories: agrees, neutral, disagrees, extends
- Use LLM only if similarity >0.5 (otherwise mark "unrelated")

### Entity Extraction Approach

**Deterministic First**
- Regex for known patterns (ministers, portfolios, NZ locations)
- Dictionary matching for common orgs ("Ministry of Health")
- Date parsing (YYYY-MM-DD, "next month")

**Statistical Fallback**
- spaCy NER (en_core_web_lg) for PERSON, ORG, GPE
- Link to canonical entities (handle "Luxon" → "Christopher Luxon")
- Co-occurrence tracking for relationship inference

**No LLM** (entity extraction is deterministic, cheaper this way)

---

## Evaluation Framework

### What We Measure

**1. Summarization Quality**
- ROUGE-L vs human-written summaries (target ≥0.40)
- Factual consistency: Do key facts appear? (target ≥0.90)
- Citation quality: Are citations from relevant sentences? (target ≥0.80)

**2. Retrieval Quality**
- NDCG@3 for top-3 cross-source links (target ≥0.70)
- Recall@5 for finding all relevant articles (target ≥0.60)

**3. Operational Metrics**
- Job success rate (target ≥99%)
- P95 latency per job type (ingest <5s, summarize <15s)
- Cost per release processed (target <$0.30)

**4. User Engagement**
- Digest open rate (target ≥30%)
- Link click-through rate (target ≥15%)
- Unsubscribe rate (target <2%)

### Evaluation Process

**Labeled Datasets** (created in Week 4, updated quarterly)
- 50 releases with human-written gold summaries
- 50 releases with labeled relevant articles (3-point relevance scale)
- 20 releases with manually tagged entities

**Automated Nightly Runs**
- Compute metrics on test set
- Compare to thresholds
- Generate report artifact
- Create GitHub issue if thresholds not met

**A/B Testing Framework**
- Route 10% of traffic to new prompt version
- Track metrics separately per version
- Statistical significance test after 100 samples
- Auto-rollback if quality drops >5%

---

## Project Timeline (16 Weeks)

### Phase 1: Foundation (Weeks 1-4)

**Week 1: Infrastructure Setup**
- Docker Compose (Postgres, Redis, Meilisearch)
- Database schema & migrations (Alembic)
- Base monitoring (Sentry, Prometheus endpoints)
- **Key Decision**: Choose between Fly.io vs Railway for hosting
- **Deliverable**: `docker-compose up` runs full stack locally

**Week 2: Ingestion Pipeline**
- RSS fetcher with error handling & rate limits
- HTML parser (BeautifulSoup + Readability)
- Text cleaning & deduplication (SHA256 IDs)
- **Key Decision**: How far back to backfill (recommend: 6 months)
- **Deliverable**: Script loads 100 historical releases

**Week 3: Job Queue System**
- BullMQ setup with Redis
- Worker framework (base classes, error handling)
- Job tracking in DB with retry logic
- **Key Decision**: Concurrency limits per worker type
- **Deliverable**: Jobs enqueued and processed reliably

**Week 4: Cost Controls & Monitoring**
- Cost calculation and circuit breaker
- Grafana dashboards (jobs, costs, errors)
- Slack/email alerting
- **Create labeled evaluation datasets** (50 summaries, 50 IR queries)
- **Deliverable**: Real-time cost dashboard operational

### Phase 2: AI Pipeline (Weeks 5-8)

**Week 5: Summarization**
- Prompt template system (DB-backed versioning)
- GPT-4o-mini integration with rate limiting
- Structured output validation
- **Key Decision**: Temperature, max tokens, prompt style
- **Deliverable**: 50 releases summarized with citations

**Week 6: Verification System**
- Claim extraction from summaries
- Evidence retrieval prompts
- Confidence scoring & auto-flagging
- **Key Decision**: Threshold for manual review (recommend: <0.7)
- **Deliverable**: Verification metrics >85% accuracy on test set

**Week 7: Fallback Mechanisms**
- TF-IDF extractive summarization (no LLM)
- Auto-fallback when budget exceeded
- Content quality filters (guardrails)
- **Test failure scenarios**: LLM down, budget exceeded, malformed outputs
- **Deliverable**: System gracefully degrades under stress

**Week 8: Search Infrastructure**
- Generate embeddings (text-embedding-3-small)
- pgvector setup + indexes
- BM25 full-text search
- Hybrid search scoring
- **Key Decision**: Embedding dimension (768 vs 1536)
- **Deliverable**: Search returns relevant results in <500ms

### Phase 3: User Features (Weeks 9-12)

**Week 9: React Native App (MVP)**
- Project setup with Expo
- List view with filters (minister, portfolio, date)
- Release detail screen (summary + source)
- Search interface
- **Key Decision**: Expo Go vs bare React Native, UI library choice
- **Deliverable**: Functional mobile app for browsing releases

**Week 10: Email Digest**
- User signup & preferences
- HTML email template (responsive)
- Daily digest job (8:30 AM NZDT)
- Unsubscribe & open tracking
- **Key Decision**: Email service (SendGrid vs Resend vs AWS SES)
- **Deliverable**: Daily email sent to test subscribers

**Week 11: Cross-Source Linking**
- News API integration (NZ Herald, Stuff, RNZ)
- Article ingestion + embeddings
- Link generation worker
- Stance detection (agree/disagree/extend)
- **Key Decision**: News API tier (free vs paid)
- **Deliverable**: Each release shows 3-5 related articles

**Week 12: Entity Extraction**
- spaCy NER pipeline
- Entity canonicalization (name matching)
- Entity detail pages
- Co-occurrence tracking
- **Deliverable**: Entity pages show mentions + related releases

### Phase 4: Production Readiness (Weeks 13-16)

**Week 13: Evaluation Suite**
- Automated metrics script (ROUGE, NDCG, factuality)
- GitHub Actions nightly eval
- Threshold checking & alerting
- **Create evaluation report template**
- **Deliverable**: Nightly metrics meet success criteria

**Week 14: Admin Tools**
- Admin panel (job control, prompt testing)
- Manual summary override UI
- Content flag resolution interface
- Entity management console (list/edit canonical entities, fix HTML/noise, merge duplicates)
- Entity mention explorer (see latest mentions with source docs, bulk delete bad ones)
- News article QA (inspect latest articles, re-fetch or delete)
- Dashboard showing key counters (release/news totals, entity counts) and freshness indicators
- Audit log of manual overrides/edits for traceability
- **Test admin workflows end-to-end**
- **Deliverable**: Non-technical admin can manage system

**Week 15: Production Deployment**
- Deploy to Fly.io (or chosen platform)
- Production secrets & env vars
- Database backup automation
- SSL & domain setup
- **Load testing**: 200 concurrent users
- **Deliverable**: System live at production URL

**Week 16: Launch & Documentation**
- Complete architecture docs
- API documentation (OpenAPI)
- Runbooks (incident response)
- Demo video (5 min)
- Public announcement
- **Week 16 is buffer for unexpected issues**
- **Deliverable**: Handoff package for maintainers

---

## Technical Stack Decisions

### Core Technologies (Locked In)

**Backend**
- Language: Python 3.11+ (for ML/NLP ecosystem)
- Framework: FastAPI (async, OpenAPI auto-gen)
- ORM: SQLAlchemy 2.0 (with Alembic migrations)
- Task Queue: BullMQ (Redis-backed, best-in-class)

**Database**
- Primary: Postgres 16 (pgvector for embeddings)
- Cache: Redis 7 (queue + caching)
- Search: Meilisearch 1.11 (fast full-text, easy ops)

**Frontend**
- Framework: React Native (with Expo for faster development)
- UI Library: React Native Paper or NativeWind (Tailwind for RN)
- State: React Query (server state) + Zustand (client state)
- Navigation: React Navigation 6

**AI/ML**
- LLM: OpenAI GPT-4o-mini (cost-effective)
- Embeddings: text-embedding-3-small (768d)
- NER: spaCy en_core_web_lg (offline, fast)
- Validation: Zod (runtime schema validation)

**Infrastructure**
- Hosting: Fly.io (Postgres, Redis, app all in one)
- Monitoring: Grafana Cloud (free tier) + Sentry
- CI/CD: GitHub Actions
- Storage: MinIO self-hosted (or S3 if budget allows)

### Decisions Still Open

**Email Service** (Choose in Week 10)
- Option A: Resend ($0, 3k emails/month free) ← Recommended
- Option B: SendGrid ($15/mo, 40k emails/month)
- Option C: AWS SES ($0.10/1k emails, complex setup)

**News API** (Choose in Week 11)
- Option A: NewsAPI.org (Free tier: 100 req/day) ← Start here
- Option B: Bing News Search API ($7/1k queries)
- Option C: Custom RSS aggregator (free, more work)

**Deployment Platform** (Finalize in Week 1)
- Option A: Fly.io ($25/mo, all-in-one) ← Recommended
- Option B: Railway ($20/mo, simpler UX)
- Option C: AWS (cheapest long-term, highest complexity)

### React Native Specific Considerations

**Why React Native Over Web?**
- **Native mobile experience** - Better performance, offline capabilities, push notifications
- **Cross-platform** - Single codebase for iOS and Android
- **Engagement** - Push notifications for breaking releases can drive daily active usage
- **Offline-first** - Cache summaries locally, sync when online

**Development Approach**
- **Start with Expo** - Faster development, easier setup, managed workflow
- **Eject later if needed** - Only if you need native modules not in Expo
- **Expo Router** - File-based routing like Next.js, familiar pattern
- **EAS Build** - Cloud builds for iOS/Android without Mac required

**Key Technical Decisions**

**Option 1: Expo Managed (Recommended for MVP)**
- Pros: Fastest setup, OTA updates, no Xcode/Android Studio needed
- Cons: Limited to Expo modules, ~50MB app size
- Best for: Getting to market quickly, testing concept

**Option 2: Bare React Native**
- Pros: Full native module access, smaller bundle size
- Cons: More setup, need Mac for iOS builds, slower iteration
- Best for: Production app with custom requirements

**UI Library Choice**
- Option A: React Native Paper (Material Design) ← Start here
- Option B: NativeWind (Tailwind for RN, familiar if you know Tailwind)
- Option C: React Native Elements
- Option D: Custom with Reanimated (most performant, most work)

**State Management Strategy**
- **Server state**: React Query (same as web, works great)
- **Local state**: Zustand (lightweight, easy)
- **Persistent state**: AsyncStorage wrapped in Zustand persist
- **Cache strategy**: Cache release list, summaries, and entity data locally

**Offline Strategy**
```
Online Mode:
- Fetch latest releases from API
- Display with real-time data
- Push notifications for new releases

Offline Mode:
- Show cached releases (last 50)
- Grey out search (requires API)
- Enable reading saved/bookmarked releases
- Queue actions (bookmark, share) for sync
```

**Push Notifications Architecture**
```
New Release Ingested → Trigger Cloud Function
    ↓
Check User Preferences (portfolios of interest)
    ↓
Send Push via Expo Push Notifications
    ↓
User Taps → Deep link to Release Detail
```

**Performance Considerations**
- **List virtualization**: Use FlashList (faster than FlatList)
- **Image optimization**: Use expo-image (WebP, caching, lazy load)
- **Bundle size**: Code splitting with React.lazy() where possible
- **Startup time**: Minimize work in app initialization (<1s to interactive)

**Platform-Specific Features**
- iOS: Share extension (share articles to app)
- Android: Home screen widget (today's releases)
- Both: Biometric authentication for saved preferences
- Both: System dark mode support

**Development Workflow**
```bash
# Local dev (runs on iOS Simulator + Android Emulator + physical device)
npx expo start

# OTA updates (push fixes without app store)
eas update --branch production

# Build for app stores
eas build --platform all
```

**Testing Strategy for Mobile**
- **Unit tests**: Jest (same as web)
- **Component tests**: React Native Testing Library
- **E2E tests**: Detox (more stable than Appium)
- **Manual testing**: TestFlight (iOS) + Internal testing (Android)

**App Store Considerations**
- **iOS review time**: 24-48 hours typically
- **Android review time**: Few hours typically
- **Beta testing**: TestFlight (iOS), Internal testing (Android)
- **Versioning**: Semantic versioning (1.0.0, 1.0.1, 1.1.0)

**Monetization Options** (if applicable)
- No ads in MVP (better user experience)
- In-app purchase for "Pro" features (React Native IAP)
- Subscription model via RevenueCat (handles iOS/Android complexity)

**Analytics & Monitoring**
- Expo Analytics (built-in, basic)
- Sentry for crash reporting (mobile SDK)
- PostHog for product analytics (open source)
- Firebase Analytics (free, comprehensive)

---

## Operational Readiness

### Monitoring Strategy

**What to Monitor**
1. **Business Metrics**: Releases ingested, summaries generated, emails sent
2. **Performance**: API latency (P50/P95/P99), job duration, search speed
3. **Costs**: Hourly/daily spend, tokens used, circuit breaker events
4. **Reliability**: Job success rate, error rate, queue depth
5. **User Engagement**: Digest opens, clicks, unsubscribes

**Alerting Rules**
- **Critical**: Circuit breaker open, hourly budget exceeded, job failure rate >5%
- **Warning**: Daily budget at 90%, queue backlog >100, no ingestions in 2 hours
- **Info**: New release ingested, digest sent, eval metrics updated

**Dashboard Design**
- Overview: System health at a glance (green/yellow/red indicators)
- Jobs: Success rate, duration trends, current queue depth
- Costs: Spend vs budget (hourly/daily/monthly), cost per operation
- Quality: Verification scores, ROUGE metrics, user engagement

### Incident Response

**Runbook: LLM API Down**
1. Circuit breaker opens automatically
2. System falls back to extractive summaries
3. Alert sent to Slack: "LLM unavailable, using fallback"
4. Check OpenAI status page
5. If outage >1 hour, notify users via dashboard banner
6. Once resolved, manually trigger reprocessing of fallback summaries

**Runbook: High Cost Alert**
1. Identify which operation is expensive (check cost dashboard)
2. Review recent prompt changes or traffic spikes
3. If unexpected: pause that worker, investigate
4. If expected (traffic surge): decide to increase budget or let circuit breaker engage
5. Document decision in GitHub issue

**Runbook: Digest Not Sent**
1. Check GitHub Actions workflow logs
2. Check job_runs table for email jobs
3. If job failed: check SMTP logs, verify credentials
4. If job succeeded but emails bounced: check user email addresses
5. Manually trigger resend if <30 min late

### Maintenance Windows

**Daily** (automated)
- 2:00 AM NZDT: Evaluation suite runs
- 8:30 AM NZDT: Daily digest sent
- Every hour: RSS fetch + ingestion

**Weekly** (manual, 1-2 hours)
- Review flagged content (manual queue)
- Check cost trends, adjust budgets if needed
- Review error logs for patterns
- Update prompt templates if quality issues

**Monthly** (manual, 2-4 hours)
- Evaluation report deep-dive
- User feedback analysis
- Database vacuum & reindex
- Update labeled test sets with new examples

**Quarterly**
- Major version updates (Next.js, Postgres, etc.)
- Prompt A/B test results review
- Feature prioritization
- Cost optimization (switch models, batch operations)

---

## Risk Management

### Technical Risks

**Risk: LLM Costs Spiral Out of Control**
- Likelihood: Medium
- Impact: High (budget blown, service shutdown)
- Mitigation: Circuit breakers, hourly limits, real-time monitoring
- Contingency: Automatic fallback to extractive summaries

**Risk: OpenAI API Rate Limits Hit**
- Likelihood: Medium (especially during traffic spikes)
- Impact: Medium (delays in processing)
- Mitigation: Rate limiting, request batching, retry with exponential backoff
- Contingency: Queue buffers requests, processes when rate limit resets

**Risk: Data Quality Issues (Bad Summaries)**
- Likelihood: High (LLMs hallucinate)
- Impact: Medium (user trust, evaluation metrics)
- Mitigation: Verification pipeline, content flags, manual review queue
- Contingency: Prompt version rollback, increase verification strictness

**Risk: RSS Feed Changes Format**
- Likelihood: Low-Medium (government sites change slowly)
- Impact: High (ingestion breaks completely)
- Mitigation: Health checks on feed structure, fallback parsers
- Contingency: Manual fixes, alert on-call engineer

**Risk: Database Performance Degrades**
- Likelihood: Medium (as data grows)
- Impact: Medium (slow UI, job timeouts)
- Mitigation: Proper indexes, query optimization, connection pooling
- Contingency: Read replicas, materialized views, archival strategy

### Operational Risks

**Risk: Solo Developer Burnout**
- Likelihood: High (16-week solo project)
- Impact: High (project stalls)
- Mitigation: Realistic timeline, built-in buffer, automate everything possible
- Contingency: Bring in second developer weeks 13-16 if needed

**Risk: Scope Creep**
- Likelihood: High ("just one more feature...")
- Impact: Medium (missed deadline)
- Mitigation: Strict MVP definition, defer nice-to-haves to post-launch
- Contingency: Cut entity extraction + cross-linking to hit Week 12 deadline

**Risk: Production Deployment Issues**
- Likelihood: Medium (first deploy always has surprises)
- Impact: Medium (delayed launch)
- Mitigation: Week 16 is full buffer for deployment issues
- Contingency: Stage environment for testing, incremental rollout

---

## Post-Launch Strategy

### Weeks 17-20: Stabilization

**Focus: Keep the lights on, fix critical bugs**
- Monitor dashboards 2x/day
- Rapid response to user-reported issues
- No new features (hardening only)
- Build up operational confidence

### Months 2-3: Optimization

**Focus: Improve quality and reduce costs**
- A/B test improved prompts
- Optimize database queries (add missing indexes)
- Experiment with cheaper models (GPT-4o-mini → GPT-3.5-turbo for some tasks?)
- Add caching for expensive operations
- **Target: Reduce monthly costs by 20%**

### Months 4-6: Feature Expansion

**Possible additions** (prioritize based on user feedback):
1. **Policy Diff Viewer**: Compare original consultation docs to final policy
2. **Stakeholder Heatmap**: Who's mentioned most in each portfolio
3. **Timeline Visualization**: Policy evolution over time
4. **Quiz/Learning Mode**: Spaced repetition for policy knowledge
5. **API for Developers**: Let others build on the data

### Long-Term Sustainability

**Revenue Model** (if needed beyond educational goal)
- Free tier: Daily digest, basic search
- Pro tier ($10/mo): Custom alerts, API access, historical data export
- Enterprise ($500/mo): White-label, dedicated support, custom training

**Maintenance Plan**
- 2 hours/week: Review flagged content, monitor costs
- 1 day/month: Updates, evaluation reviews, feature planning
- 1 week/quarter: Major upgrades, A/B tests, optimization sprints

**Handoff Readiness**
- All code documented (docstrings, architecture docs)
- Runbooks for common incidents
- Video walkthroughs of admin tasks
- Contact info for on-call support (if applicable)

---

## Appendix: Key Architectural Diagrams

### Data Flow Diagram

```
RSS Feed → Ingest Worker → Raw Release (DB)
                ↓
         Clean & Dedupe → Canonical Release (DB)
                ↓
         ┌───────┴───────┐
         ↓               ↓
    Summarize       Embed & Index
    Worker          Worker
         ↓               ↓
    Summary (DB)    Vector Store
         ↓               
    Verify          Cross-Link
    Worker          Worker
         ↓               ↓
    Verified        Links to
    Claims          Articles
         ↓               ↓
         └───────┬───────┘
                 ↓
         Dashboard / Email
```

### Cost Control Flow

```
LLM Request → Check Circuit Breaker
                ↓
         [Open?] ──Yes──→ Use Fallback Method
                ↓ No
         Check Hourly Spend
                ↓
         [>90% limit?] ──Yes──→ Open Circuit, Use Fallback
                ↓ No
         Proceed with LLM Call
                ↓
         Track: tokens, cost, latency
                ↓
         Update Rolling Spend Windows
                ↓
         Check if threshold reached
                ↓
         [Threshold?] ──Yes──→ Open Circuit, Alert Admin
```

### Evaluation Loop

```
Nightly (2 AM)
    ↓
Run Test Set (50 summaries, 50 IR queries)
    ↓
Compute Metrics (ROUGE, NDCG, factuality)
    ↓
Compare to Thresholds
    ↓
[Met?] ──No──→ Create GitHub Issue, Alert Team
    ↓ Yes
Store Results in DB
    ↓
Update Grafana Dashboard
    ↓
Weekly Report → Product Review
```

---

## Success Checklist

### Week 8 Checkpoint
- [ ] Can ingest 100 releases in <10 minutes
- [ ] Summaries generated with verification >85%
- [ ] Cost dashboard shows <$2/day spend
- [ ] Zero LLM calls without circuit breaker check

### Week 12 Checkpoint (MVP Complete)
- [ ] Daily digest sent on schedule
- [ ] Mobile app loads 100 releases in <2 seconds
- [ ] Search returns results in <500ms
- [ ] Each release has 3+ cross-source links

### Week 16 Checkpoint (Production Launch)
- [ ] Evaluation metrics meet all success criteria
- [ ] System handles 200 concurrent users
- [ ] 99% uptime over last 7 days
- [ ] Admin can manage without DB access
- [ ] Complete documentation for handoff

---

## Final Notes

This plan is **intentionally flexible** in the details—it provides the strategic direction, architectural guardrails, and quality standards, then trusts the implementation team to execute well.

**Key Philosophy**: 
- Build the simplest thing that could possibly work
- Add complexity only when necessary
- Measure everything, optimize what matters
- Design for failure (it will happen)
- Ship value early, iterate based on real usage

**When in Doubt**:
1. Does it serve the north-star goal?
2. Can we measure if it's working?
3. What happens if it fails?
4. Is there a simpler approach?

Good luck! 🚀
