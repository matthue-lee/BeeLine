import { Job } from 'bullmq';
import { BaseWorker } from './baseWorker';
import { IngestJobPayload } from '../queues/payloads';

export class IngestWorker extends BaseWorker<IngestJobPayload, { acknowledged: boolean }> {
  protected async process(job: Job<IngestJobPayload>, runId: number): Promise<{ acknowledged: boolean }> {
    this.logger.info(
      { jobId: job.id, runId, feedUrl: job.data.feed_url, sourceId: job.data.source_id },
      'Processing ingest job'
    );
    // Day 1 placeholder: simply acknowledge the job. Week 4 will connect to ingestion pipeline.
    return { acknowledged: true };
  }
}
