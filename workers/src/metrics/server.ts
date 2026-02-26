import express from 'express';
import { register } from './registry';
import { queuePublisher } from '../queues/QueuePublisher';
import { makeEmbedIdempotencyToken, makeEntityExtractIdempotencyToken, makeLinkIdempotencyToken, makeSummarizeIdempotencyToken, makeVerifyIdempotencyToken } from '../queues/tokens';

export function startMetricsServer(port: number): void {
  const app = express();
  app.use(express.json());
  app.get('/health', (_req, res) => res.json({ status: 'ok' }));
  app.get('/metrics', async (_req, res) => {
    res.set('Content-Type', register.contentType);
    res.send(await register.metrics());
  });

  // Internal enqueue endpoints for Python pipeline → BullMQ
  app.post('/internal/enqueue/:stage', async (req, res) => {
    try {
      const stage = req.params.stage as string;
      const payload = req.body || {};
      let job;
      switch (stage) {
        case 'summarize':
          if (!payload.idempotency_token && payload.release_id) {
            payload.idempotency_token = makeSummarizeIdempotencyToken(payload.release_id, payload.prompt_version_hint || 'latest');
          }
          job = await queuePublisher.enqueueSummarize(payload);
          break;
        case 'verify':
          if (!payload.idempotency_token && payload.summary_id) {
            payload.idempotency_token = makeVerifyIdempotencyToken(payload.summary_id);
          }
          job = await queuePublisher.enqueueVerify(payload);
          break;
        case 'embed':
          if (!payload.idempotency_token && payload.source_type && payload.source_id && payload.text_hash) {
            payload.idempotency_token = makeEmbedIdempotencyToken(payload.source_type, payload.source_id, payload.text_hash);
          }
          job = await queuePublisher.enqueueEmbed(payload);
          break;
        case 'link':
          if (!payload.idempotency_token && payload.release_id) {
            payload.idempotency_token = makeLinkIdempotencyToken(payload.release_id);
          }
          job = await queuePublisher.enqueueLink(payload);
          break;
        case 'entity_extract':
          if (!payload.idempotency_token && payload.source_type && payload.source_id) {
            payload.idempotency_token = makeEntityExtractIdempotencyToken(payload.source_type, payload.source_id);
          }
          job = await queuePublisher.enqueueEntityExtract(payload);
          break;
        default:
          return res.status(400).json({ error: 'unknown stage' });
      }
      return res.json({ job_id: job.id });
    } catch (err: any) {
      return res.status(500).json({ error: String(err?.message || err) });
    }
  });
  app.listen(port, () => {
    console.log(`Metrics server listening on ${port}`);
  });
}
