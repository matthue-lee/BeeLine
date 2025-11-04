**NZ Beehive Policy Brief -- Project Plan (agents.md)**
======================================================

> **Goal:** Turn Beehive.govt.nz releases into *actionable understanding* with a production‑quality pipeline, rigorous evaluation, and a clean UX. This doc is your single source of truth for scope, architecture, tasks, tests, and timelines.

* * * * *

**Table of Contents**
---------------------

1.  [North‑Star & Success Criteria](#north-star--success-criteria)

2.  [Deliverables (What You Will Ship)](#deliverables-what-you-will-ship)

3.  [System Architecture](#system-architecture)

4.  [Data Model](#data-model)

5.  [Pipelines & Agents](#pipelines--agents)

6.  [LLM Prompts & Guardrails](#llm-prompts--guardrails)

7.  [Evaluation Plan](#evaluation-plan)

8.  [Analytics & Telemetry](#analytics--telemetry)

9.  [Security, Ethics, Compliance](#security-ethics-compliance)

10. [Project Timeline (Weeks 1--8)](#project-timeline-weeks-1%E2%80%938)

11. [Repository Structure](#repository-structure)

12. [Local Dev: Setup & Commands](#local-dev-setup--commands)

13. [CI/CD & Schedules](#cicd--schedules)

14. [Testing Strategy](#testing-strategy)

15. [Dashboard UX Spec](#dashboard-ux-spec)

16. [Stretch Tracks](#stretch-tracks)

17. [FAQ & Troubleshooting](#faq--troubleshooting)

* * * * *

**North‑Star & Success Criteria**
---------------------------------

-   **Practical:** Daily brief that surfaces *what changed*, *why it matters*, and *what to read next*.

-   **Educational:** Demonstrate ETL, retrieval, LLM/NLP, agent orchestration, evaluation, and UI.

-   **Responsible:** Cite sources, track uncertainty, and enable verification.

**Success criteria**

-   T+60s after a new release appears in RSS → stored, summarized, and visible in dashboard.

-   Daily email with: 1) bullet summary, 2) "why it matters", 3) cross‑source links w/ stance tags.

-   ≥90% of claims in summaries traceable to an exact sentence in sources (auto‑verifier pass).

-   Measurable IR quality (e.g., NDCG@3 ≥ 0.7 on labeled set of 50 releases).

* * * * *

**Deliverables (What You Will Ship)**
-------------------------------------

1.  **Ingestion service** (Python) -- idempotent RSS fetcher, parser, deduper.

2.  **Processing workers** -- summarizer, cross‑source linker, entity extractor, verifier.

3.  **Vector + text search** -- BM25 + embeddings hybrid (Meilisearch + pgvector or Qdrant).

4.  **Next.js dashboard** -- filters, timelines, entity pages, side‑by‑side comparisons.

5.  **Daily email digest** -- HTML digest + optional Anki export (CSV/TSV).

6.  **Agent graph** -- MCP tools + LangGraph FSM with guardrails.

7.  **Evaluation suite** -- scripts, labeled sets, metrics report.

8.  **Infra** -- Docker Compose, GitHub Actions (cron), Sentry/Prometheus.

* * * * *

**System Architecture**
-----------------------

```
                ┌───────────────────────────────────────────────────────────┐
                │                           Scheduler                      │
                │ (GitHub Actions cron / systemd timer / Celery beat)      │
                └───────────────┬───────────────────────────┬──────────────┘
                                │                           │
                          [feed_fetch]                 [backfill]
                                │                           │
┌─────────────┐   RSS     ┌─────▼─────┐  raw JSON  ┌────────▼─────────┐
│ beehive.gov │──────────▶│ Ingestor  │───────────▶│ Postgres (RAW)   │
└─────────────┘           │  (Python) │            │  + S3/MinIO blob │
                           └─────┬─────┘            └────────┬─────────┘
                                 │ normalize/clean            │
                                 ▼                           ▼
                          ┌────────────┐              ┌──────────────┐
                          │  Canonical │              │ Parsed tables │
                          │  (hash/id) │              │ + embeddings  │
                          └─────┬──────┘              └──────┬───────┘
                                │                             │
         ┌───────────────────────┼─────────────────────────────┼───────────────────────────┐
         │                       │                             │                           │
         ▼                       ▼                             ▼                           ▼
  [summarize]             [cross_search]                 [extract_entities]         [verify_claims]
 (LLM w/ guard)            (news APIs+IR)               (spaCy/transformers)        (Q&A against src)
         │                       │                             │                           │
         └──────────────┬────────┴───────────┬─────────────────┴───────────┬───────────────┘
                        ▼                    ▼
                 ┌────────────┐       ┌──────────────┐         citations/flags
                 │  Summaries │◀─────▶│ Links/Compar │───────────────────────┐
                 └─────┬──────┘       └─────┬────────┘                       │
                       │                    │                                  │
                       ▼                    ▼                                  ▼
                 ┌─────────────┐     ┌──────────────┐                   ┌────────────┐
                 │ Next.js UI  │     │ Email Digest │                   │  Metrics   │
                 │  (shadcn)   │     │  (HTML/Anki) │                   │  & Logs    │
                 └─────────────┘     └──────────────┘                   └────────────┘
```

* * * * *

**Data Model**
--------------

**Tables (Postgres)**

-   release(id, title, url, published_at, minister, portfolio, text_raw, text_clean, embeddings vector)

-   article(id, source, url, published_at, text, embeddings vector)

-   link(release_id, article_id, similarity real, rationale text)

-   entity(id, name, type) -- types: PERSON, ORG, POLICY, COUNTRY, DATE

-   mention(doc_id, doc_type, entity_id, span int4range, sentence text)

-   summary(doc_id, doc_type, short text, why_it_matters text, citations jsonb, model_verdict jsonb)

-   quiz(card_id, doc_id, type, prompt, answer, distractors jsonb)

-   job_run(id, name, started_at, finished_at, status, details jsonb)

**Indexes**

-   GIN on to_tsvector('english', text_clean) for BM25.

-   HNSW/IVFFlat on embeddings (pgvector).

-   Btree on published_at, minister, portfolio.

* * * * *

**Pipelines & Agents**
----------------------

### **Deterministic jobs**

-   **Ingestor**: fetch RSS, resolve article URL, download HTML, sanitize, strip boilerplate, persist RAW and PARSED; compute canonical ID: sha256(title + url).

-   **Embedder**: create dense vectors for paragraphs/chunks; store mean pooled doc vector + chunk vectors in child table if needed.

### **Agent graph (LangGraph + MCP)**

Tools exposed via MCP so any LLM/agent can call them:

-   feed_fetch({max_items, since}) -> releases[]

-   cross_search({query, k}) -> articles[] (BM25+embeddings hybrid over local + optional news API)

-   summarize({doc_id, style, max_tokens}) -> {short, why_it_matters, citations[]}

-   verify({doc_id, claims[]}) -> {supported[], unsupported[]} (answers: which sentence supports claim?)

-   mail({subject, html, recipients[]}) -> status

**State machine**

1.  Fetch → 2. Canonicalize/Dedupe → 3. Summarize (draft) → 4. Verify (drop unsupported claims) → 5. Cross‑search + compare → 6. Store + Publish (UI + Email).

* * * * *

**LLM Prompts & Guardrails**
----------------------------

### **Summary (few‑shot, JSON‑schema forced)**

-   **System:** "You are a neutral NZ policy brief writer. Output JSON matching the schema."

-   **User:** full cleaned text + metadata.

-   **JSON schema:**

```
{
  "type": "object",
  "properties": {
    "short": {"type": "string", "maxLength": 480},
    "why_it_matters": {"type": "string", "maxLength": 600},
    "claims": {"type": "array", "items": {"type": "string"}},
    "citations": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["short", "why_it_matters", "claims", "citations"]
}
```

### **Verifier (closed‑book → open‑book)**

-   For each claim, run retrieval on the source doc; ask: *"Return the exact sentence that supports this claim, or **null**."*Unsupported → drop or flag.

### **Cross‑source comparison prompt**

-   Inputs: release summary + top‑k external snippets.

-   Outputs: agreement_points[], disagreements[], new_info[], each with direct quotes + URLs.

### **Content policies**

-   Always cite URLs; prefer direct quotes for factual assertions; prohibit speculation.

* * * * *

**Evaluation Plan**
-------------------

-   **IR:** Label 50 releases with 5 relevant news links each; compute NDCG@3/5 and Recall@5.

-   **Summarization factuality:** Q&A style (QAFactEval): generate 5 questions per summary; check answers retrievable from source.

-   **Extraction:** Hand‑label entities/relations on 20 docs; report precision/recall/F1.

-   **User value:** Track reading time saved (length of sources vs brief), 7‑day quiz retention.

-   **Operational:** SLA: 99% jobs < 60s; error rate < 1%/day; coverage % of releases processed.

* * * * *

**Analytics & Telemetry**
-------------------------

-   **Metrics:** per‑stage latency, failure counts, verification pass‑rate, hallucination flags, CTR on cross‑links, quiz completions.

-   **Tools:** Prometheus + Grafana (docker), Sentry for exceptions, structured logs (JSON) with request IDs.

* * * * *

**Security, Ethics, Compliance**
--------------------------------

-   Use **RSS** and official pages; respect robots & rate limits.

-   Store only public content; no personal data.

-   Mark AI‑generated sections; provide one‑click "view source context".

-   Keep model prompts and outputs in DB for audit.

* * * * *

**Project Timeline (Weeks 1--8)**
--------------------------------

**Week 1: MVP Ingestion**

-   Docker Compose (Postgres, Meilisearch, MinIO optional).

-   Ingestor + canonical IDs + text cleaning; basic schema migrations (Alembic).

-   Endpoint: POST /admin/ingest/run.

**Week 2: Summaries + Daily Email + Minimal UI**

-   LLM summarizer + verifier pass; HTML email template.

-   Next.js: list view, search, filters (minister/portfolio/date).

**Week 3: Hybrid Search & Cross‑source Compare**

-   Embeddings + BM25; link 2--5 stories per release; side‑by‑side UI.

**Week 4: Evaluation Harness**

-   Label sets + metrics scripts; nightly metrics report artifact.

**Week 5: Entity Extraction & Timeline**

-   IE pipeline; entity pages; timeline by portfolio.

**Week 6: Agent Graph (MCP)**

-   Implement MCP tools; deterministic LangGraph orchestration; retries/timeouts.

**Week 7: Learning Companion**

-   Quiz generation; Anki CSV export; spaced repetition logic.

**Week 8: Polish & Stretch**

-   Metrics dashboards, docs, demo video, and public notes site.

* * * * *

**Repository Structure**
------------------------

```
beehive-brief/
├─ apps/
│  ├─ api/               # FastAPI service (ingest, summarize, verify, links)
│  └─ web/               # Next.js dashboard (shadcn/ui)
├─ packages/
│  ├─ agents/            # LangGraph flows + MCP tool adapters
│  ├─ nlp/               # prompts, IE, verification, eval
│  └─ common/            # shared utils, schemas
├─ infra/
│  ├─ docker-compose.yml
│  ├─ migrate/           # Alembic migrations
│  └─ github/            # Actions workflows
├─ data/
│  └─ labeled_sets/      # eval gold data
├─ scripts/
│  ├─ backfill.py
│  └─ eval_report.py
└─ README.md / agents.md / ARCHITECTURE.md
```

* * * * *

**Local Dev: Setup & Commands**
-------------------------------

**.env.example** (root)

```
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/beehive
MEILISEARCH_HOST=http://meili:7700
MEILISEARCH_KEY=dev_key
OPENAI_API_KEY=sk-...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@example.com
SMTP_PASS=app_password
DIGEST_TO=you@example.com
```

**docker-compose.yml (snippet)**

```
version: '3.9'
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: beehive
    ports: ["5432:5432"]
  meili:
    image: getmeili/meilisearch:v1.11
    environment:
      MEILI_MASTER_KEY: dev_key
    ports: ["7700:7700"]
  api:
    build: ./apps/api
    env_file: .env
    depends_on: [db, meili]
    ports: ["8000:8000"]
  web:
    build: ./apps/web
    env_file: .env
    depends_on: [api]
    ports: ["3000:3000"]
```

**Makefile (common tasks)**

```
setup: ## install local deps
	uv pip install -r requirements.txt

dev: ## run api + web locally
	docker compose up --build

migrate: ## run DB migrations
	alembic upgrade head

backfill: ## load historical releases
	python scripts/backfill.py --since 2024-01-01
```

* * * * *

**CI/CD & Schedules**
---------------------

**GitHub Actions: nightly + hourly**

```
name: pipeline
on:
  schedule:
    - cron: '0 * * * *'      # hourly ingest
    - cron: '30 20 * * *'    # 08:30 NZDT daily digest
  workflow_dispatch: {}
jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1
      - run: uv pip install -r requirements.txt
      - env:
          DATABASE_URL: ${{secrets.DATABASE_URL}}
          OPENAI_API_KEY: ${{secrets.OPENAI_API_KEY}}
        run: python -m apps.api.jobs.ingest_once
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1
      - run: uv pip install -r requirements.txt
      - env:
          DATABASE_URL: ${{secrets.DATABASE_URL}}
          SMTP_HOST: ${{secrets.SMTP_HOST}}
          SMTP_USER: ${{secrets.SMTP_USER}}
          SMTP_PASS: ${{secrets.SMTP_PASS}}
          DIGEST_TO: ${{secrets.DIGEST_TO}}
        run: python -m apps.api.jobs.send_digest
```

* * * * *

**Testing Strategy**
--------------------

-   **Unit:** parsers, cleaners, hash IDs, prompt formatters, schema validators.

-   **Integration:** end‑to‑end on a tiny fixture RSS; snapshot test summaries (redact timestamps/keys).

-   **IR eval:** deterministic seed for embeddings; metrics scripts produce CSV + chart.

-   **Contract tests:** MCP tool JSON schemas; LangGraph path tests (happy path + retries + timeouts).

-   **Load:** 100 releases batch; ensure < 60s latency, memory steady.

**Pytest layout**

```
tests/
  unit/
  integration/
  contracts/
  eval/
```

* * * * *

**Dashboard UX Spec**
---------------------

-   **Home:** filter by minister/portfolio/date; cards show: title, 3‑bullet summary, why‑it‑matters, chips for entities; badges for *Verified*.

-   **Compare tab:** left: Beehive; right: top external article; middle badges: *agreement/disagreement/new info* with quotes.

-   **Timeline:** per‑portfolio timeline with density plot; click to drill down.

-   **Entity page:** show all mentions, related releases, co‑occurring entities, stance trend.

* * * * *

**Stretch Tracks**
------------------

1.  **Policy Diff & Impact Explorer** -- semantic diff for linked consultation/bill PDFs; stakeholder heatmap.

2.  **Framing/Modality** -- detect frames (economy/security/fairness), hedging vs commitment.

3.  **Learning Companion** -- Anki CSV export + spaced repetition scheduling.

4.  **Magic Mirror Module** -- bottom‑center ticker with QR to open full brief.

* * * * *

**FAQ & Troubleshooting**
-------------------------

-   **HTML changed / missing fields?** Fallback to RSS + page DOM via Readability; keep strict timeouts.

-   **Model drift?** Pin base model + temperature; add golden tests for prompts.

-   **Hallucinations?** Verifier step mandatory; UI shows support sentences + links.

-   **Costs?** Cache embeddings; summarize once per doc; use small model for drafts and larger only after verifier pass.

* * * * *

### **Appendix A -- SQL DDL (starter)**

```
create extension if not exists vector;
create table release (
  id text primary key,
  title text not null,
  url text not null,
  published_at timestamptz,
  minister text,
  portfolio text,
  text_raw text,
  text_clean text,
  embeddings vector(768)
);
create table article (
  id text primary key,
  source text,
  url text,
  published_at timestamptz,
  text text,
  embeddings vector(768)
);
create table link (
  release_id text references release(id),
  article_id text references article(id),
  similarity real,
  rationale text,
  primary key (release_id, article_id)
);
```

### **Appendix B -- MCP Tool Contracts (TypeBox)**

```
export const SummarizeSchema = Type.Object({
  short: Type.String({ maxLength: 480 }),
  why_it_matters: Type.String({ maxLength: 600 }),
  claims: Type.Array(Type.String()),
  citations: Type.Array(Type.String()),
});
```

### **Appendix C -- Email Digest Template (MJML-ish)**

```
<h1>NZ Policy Brief -- {{date}}</h1>
{{#each releases}}
  <h2><a href="{{this.url}}">{{this.title}}</a></h2>
  <p><em>{{this.published_at}}</em></p>
  <ul>
    {{#each this.summary.bullets}}<li>{{this}}</li>{{/each}}
  </ul>
  <p><strong>Why it matters:</strong> {{this.summary.why_it_matters}}</p>
  <p>Related coverage: {{#each this.links}}<a href="{{this.url}}">{{this.source}}</a>{{/each}}</p>
  <hr/>
{{/each}}
```

* * * * *
