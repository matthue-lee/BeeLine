import { Job } from 'bullmq';
import { BaseWorker } from './baseWorker';
import { IngestJobData } from '../types/jobs';

export class IngestWorker extends BaseWorker<IngestJobData, { acknowledged: boolean }> {
  protected async process(job: Job<IngestJobData>, runId: number): Promise<{ acknowledged: boolean }> {
    this.logger.info({ jobId: job.id, runId, releaseId: job.data.releaseId }, 'Processing ingest job');
    // Day 1 placeholder: simply acknowledge the job. Week 4 will connect to ingestion pipeline.
    return { acknowledged: true };
  }
}
