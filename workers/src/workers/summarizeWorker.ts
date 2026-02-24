import { Job } from 'bullmq';
import { BaseWorker } from './baseWorker';
import { SummarizeJobPayload } from '../queues/payloads';

export class SummarizeWorker extends BaseWorker<SummarizeJobPayload, { releaseId: string; status: string }> {
  protected async process(job: Job<SummarizeJobPayload>, runId: number): Promise<{ releaseId: string; status: string }> {
    this.logger.info({ jobId: job.id, runId, releaseId: job.data.release_id }, 'Processing summarize job placeholder');
    // Placeholder: In Week 5 this will call LLM summarization. For now we just echo the releaseId.
    return { releaseId: job.data.release_id, status: 'queued' };
  }
}
