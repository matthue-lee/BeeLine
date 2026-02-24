export interface IngestJobPayload {
  feed_url: string;
  source_id: string;
  triggered_by: 'cron' | 'manual' | 'backfill';
}

export interface SummarizeJobPayload {
  release_id: string;
  prompt_version_hint?: string;
  priority?: number;
  idempotency_token: string;
}

export interface VerifyJobPayload {
  summary_id: string;
  claim_batch: string[];
  release_id: string;
  idempotency_token: string;
}

export interface EmbedJobPayload {
  source_type: 'release' | 'article';
  source_id: string;
  text_hash: string;
  idempotency_token: string;
}

export interface LinkJobPayload {
  release_id: string;
  candidate_article_ids: string[];
  idempotency_token: string;
}

export interface EntityExtractJobPayload {
  source_type: 'release' | 'article' | 'summary';
  source_id: string;
  idempotency_token: string;
}
