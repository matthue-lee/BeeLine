export interface BaseJobData extends Record<string, unknown> {
  releaseId?: string;
  payload?: Record<string, unknown>;
}

export interface SummarizeJobData extends BaseJobData {
  releaseId: string;
}

export interface IngestJobData extends BaseJobData {
  feedUrl?: string;
}
