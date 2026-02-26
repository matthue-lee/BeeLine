import { QueueEvents } from 'bullmq';
import pino from 'pino';
import { queuePublisher } from '../queues/QueuePublisher';
import { makeLinkIdempotencyToken, makeVerifyIdempotencyToken } from '../queues/tokens';

const logger = pino({ name: 'orchestrator' });

const connection = {
  host: process.env.REDIS_HOST || '127.0.0.1',
  port: Number(process.env.REDIS_PORT || '6379')
};

export function startOrchestrator(): void {
  const summarizeEvents = new QueueEvents('summarize', { connection });
  const embedEvents = new QueueEvents('embed', { connection });

  summarizeEvents.on('completed', async ({ jobId, returnvalue }) => {
    try {
      const result = coerceJson(returnvalue);
      const summaryId: string | undefined = result.summary_id || result.summaryId || undefined;
      const releaseId: string | undefined = result.release_id || result.releaseId || undefined;
      const claimBatch: string[] = Array.isArray(result.claim_batch) ? result.claim_batch : [];
      if (!summaryId || !releaseId) {
        logger.warn({ jobId }, 'summarize completed without summaryId/releaseId; skipping verify dispatch');
        return;
      }
      await queuePublisher.enqueueVerify({
        summary_id: summaryId,
        claim_batch: claimBatch,
        release_id: releaseId,
        idempotency_token: makeVerifyIdempotencyToken(summaryId)
      });
    } catch (err) {
      logger.error({ jobId, err }, 'Error in summarize->verify chaining');
    }
  });

  embedEvents.on('completed', async ({ jobId, returnvalue }) => {
    try {
      const result = coerceJson(returnvalue);
      const releaseId: string | undefined = result.release_id || result.releaseId || undefined;
      const candidates: string[] = Array.isArray(result.candidate_article_ids) ? result.candidate_article_ids : [];
      if (!releaseId) {
        logger.warn({ jobId }, 'embed completed without releaseId; skipping link dispatch');
        return;
      }
      await queuePublisher.enqueueLink({
        release_id: releaseId,
        candidate_article_ids: candidates,
        idempotency_token: makeLinkIdempotencyToken(releaseId)
      });
    } catch (err) {
      logger.error({ jobId, err }, 'Error in embed->link chaining');
    }
  });

  summarizeEvents.on('failed', ({ jobId, failedReason }) => {
    logger.warn({ jobId, failedReason }, 'summarize failed event');
  });
  embedEvents.on('failed', ({ jobId, failedReason }) => {
    logger.warn({ jobId, failedReason }, 'embed failed event');
  });
}

function coerceJson(value: any): any {
  if (typeof value === 'string') {
    try {
      return JSON.parse(value);
    } catch {
      return {};
    }
  }
  return value ?? {};
}

