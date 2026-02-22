export interface AdminUserProfile {
  id: string;
  email: string;
  role: string;
  display_name: string | null;
  last_login_at: string | null;
}

export interface ReleaseInfo {
  id: string;
  title: string;
  url: string;
  published_at: string | null;
  minister: string | null;
  portfolio: string | null;
  categories: string[];
  status: string;
  word_count: number | null;
  clean_excerpt: string | null;
  raw_excerpt: string | null;
  dedupe_hash: string;
  rss_metadata: Record<string, unknown>;
}

export interface IngestionInfo {
  fetched_at: string | null;
  last_updated_at: string | null;
  queue_latency_ms: number | null;
  last_ingest_job: {
    id: number;
    job_type: string;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    duration_ms: number | null;
  } | null;
}

export interface LLMOutputs {
  model: string;
  prompt_version: string | null;
  tokens_used: number | null;
  cost_usd: number | null;
  summary: {
    short: string;
    why_it_matters: string | null;
    claims: unknown[];
  };
  raw_response: Record<string, unknown> | null;
}

export interface VerificationClaimRow {
  claim_id: string;
  index: number;
  text: string;
  citations: string[];
  category: string | null;
  verification: {
    verdict: string | null;
    confidence: number | null;
    supporting_sentence: string | null;
    supporting_index: number | null;
    fallback: boolean;
  };
}

export interface EntitySnapshotItem {
  entity_id: string;
  canonical_name: string;
  entity_type: string;
  mentions: number;
  span_text: string;
  detector: string;
}

export interface EntitySnapshot {
  release: EntitySnapshotItem[];
  articles: Array<{
    article_id: string;
    title: string | null;
    entities: EntitySnapshotItem[];
  }>;
}

export interface CrossLinkRow {
  article_id: string;
  title: string;
  source: string;
  url: string;
  published_at: string | null;
  bm25_score: number | null;
  embedding_score: number | null;
  hybrid_score: number;
  stance: string | null;
  stance_confidence: number | null;
  snippet: string | null;
  cache_only: boolean;
}

export interface ReleaseDebugResponse {
  release: ReleaseInfo;
  ingestion: IngestionInfo;
  llm_outputs: LLMOutputs | null;
  verification: {
    claims: VerificationClaimRow[];
  };
  entity_snapshot: EntitySnapshot;
  cross_links: CrossLinkRow[];
  fallbacks: {
    summary_template: boolean;
    verification_skipped: boolean;
    crosslink_cache_only: boolean;
  };
}

export interface IngestionRunRecord {
  id: number;
  started_at: string | null;
  finished_at: string | null;
  status: string | null;
  source: string | null;
  total_items: number;
  inserted: number;
  updated: number;
  skipped: number;
  failed: number;
}

export interface SystemOverviewResponse {
  since: string;
  generated_at: string;
  counters: {
    releases_total: number;
    releases_last_window: number;
    articles_last_window: number;
    entity_mentions_last_window: number;
    open_flags: number;
  };
  last_ingestion: IngestionRunRecord | null;
  job_breakdown: Array<{ job_type: string; status: string; count: number }>;
  recent_jobs: Array<{
    id: number;
    job_type: string;
    status: string;
    started_at: string | null;
    duration_ms: number | null;
  }>;
}

export interface IngestionRunsResponse {
  items: IngestionRunRecord[];
  limit: number;
}

export interface EntityListItem {
  id: string;
  canonical_name: string;
  entity_type: string;
  verified: boolean;
  mention_count: number;
  last_seen: string | null;
}

export interface EntitiesResponse {
  items: EntityListItem[];
  limit: number;
  offset: number;
}

export interface EntityDetailResponse {
  entity: {
    id: string;
    canonical_name: string;
    entity_type: string;
    info: Record<string, unknown>;
    verified: boolean;
    mention_count: number;
    first_seen: string | null;
    last_seen: string | null;
  };
  aliases: Array<{ alias: string; normalized_alias: string; source: string | null; confidence: number }>;
  statistics:
    | {
        mentions_total: number | null;
        mentions_last_7d: number | null;
        mentions_last_30d: number | null;
        top_cooccurrences: Record<string, unknown> | null;
      }
    | null;
  mentions: Array<{
    id: string;
    text: string;
    source_type: string;
    source_id: string;
    detector: string;
    confidence: number;
    created_at: string | null;
  }>;
  cooccurrences: Array<{
    partner_id: string;
    partner_name: string;
    count: number;
    relationship_type: string | null;
    last_seen: string | null;
  }>;
}

export interface FlagRecord {
  id: number;
  source_type: string;
  source_id: string;
  flag_type: string;
  severity: string | null;
  resolved: boolean;
  created_at: string | null;
}

export interface FlagsResponse {
  items: FlagRecord[];
}

export interface JobRunRecord {
  id: number;
  job_type: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface JobRunsResponse {
  items: JobRunRecord[];
}

export interface CostSummaryResponse {
  hours: number;
  since: string;
  aggregates: Array<{
    operation: string;
    model: string;
    calls: number;
    tokens: number;
    cost_usd: number;
  }>;
  daily_totals: Array<{
    date: string;
    operation: string;
    total_calls: number;
    total_tokens: number;
    total_cost_usd: number;
  }>;
}

export interface LlmCallRecord {
  id: number;
  operation: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  latency_ms: number | null;
  created_at: string | null;
}

export interface LlmCallsResponse {
  items: LlmCallRecord[];
  limit: number;
}

export interface SummariesResponse {
  items: Array<{
    summary_id: number;
    release_id: string;
    release_title: string;
    prompt_version: string | null;
    model: string;
    verification_score: number | null;
    cost_usd: number | null;
    tokens_used: number | null;
    created_at: string | null;
  }>;
  limit: number;
}

export interface ArticlesResponse {
  items: Array<{
    id: string;
    title: string;
    source: string;
    url: string;
    published_at: string | null;
    summary: string | null;
    word_count: number | null;
  }>;
  limit: number;
}
