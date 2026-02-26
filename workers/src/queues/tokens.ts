import { createHash } from 'crypto';

export function makeIdempotencyToken(stage: string, inputs: Record<string, string>): string {
  // Deterministic token from stage + sorted inputs
  const payload: Record<string, string> = { stage, ...inputs };
  const ordered: Record<string, string> = {};
  Object.keys(payload)
    .sort()
    .forEach((k) => {
      ordered[k] = payload[k];
    });
  const json = JSON.stringify(ordered);
  return createHash('sha256').update(json).digest('hex');
}

export const makeSummarizeIdempotencyToken = (releaseId: string, promptVersionHint = 'latest') =>
  makeIdempotencyToken('summarize', { release_id: releaseId, prompt_version_hint: promptVersionHint });

export const makeVerifyIdempotencyToken = (summaryId: string) =>
  makeIdempotencyToken('verify', { summary_id: summaryId });

export const makeEmbedIdempotencyToken = (sourceType: string, sourceId: string, textHash: string) =>
  makeIdempotencyToken('embed', { source_type: sourceType, source_id: sourceId, text_hash: textHash });

export const makeLinkIdempotencyToken = (releaseId: string) =>
  makeIdempotencyToken('link', { release_id: releaseId });

export const makeEntityExtractIdempotencyToken = (sourceType: string, sourceId: string) =>
  makeIdempotencyToken('entity_extract', { source_type: sourceType, source_id: sourceId });

