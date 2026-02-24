import type {
  IngestJobPayload,
  SummarizeJobPayload,
  VerifyJobPayload,
  EmbedJobPayload,
  LinkJobPayload,
  EntityExtractJobPayload
} from '../queues/payloads';

export type BaseJobData = Record<string, unknown>;
export type SummarizeJobData = SummarizeJobPayload;
export type IngestJobData = IngestJobPayload;
export type VerifyJobData = VerifyJobPayload;
export type EmbedJobData = EmbedJobPayload;
export type LinkJobData = LinkJobPayload;
export type EntityExtractJobData = EntityExtractJobPayload;
