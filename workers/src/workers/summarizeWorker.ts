import { Job } from 'bullmq';
import { BaseWorker } from './baseWorker';
import { SummarizeJobData } from '../types/jobs';

export class SummarizeWorker extends BaseWorker<SummarizeJobData, { releaseId: string; status: string }> {
  protected async process(job: Job<SummarizeJobData>, runId: number): Promise<{ releaseId: string; status: string }> {
    this.logger.info({ jobId: job.id, runId, releaseId: job.data.releaseId }, 'Processing summarize job placeholder');
    // Placeholder: In Week 5 this will call LLM summarization. For now we just echo the releaseId.
    return { releaseId: job.data.releaseId, status: 'queued' };
  }
}
