import { Job } from 'bullmq';
import { BaseWorker } from './baseWorker';
import { SummarizeJobPayload } from '../queues/payloads';

export class SummarizeWorker extends BaseWorker<
  SummarizeJobPayload,
  { release_id: string; summary_id: string; claim_batch: string[]; status: string }
> {
  protected async process(
    job: Job<SummarizeJobPayload>,
    runId: number
  ): Promise<{ release_id: string; summary_id: string; claim_batch: string[]; status: string }> {
    this.logger.info({ jobId: job.id, runId, releaseId: job.data.release_id }, 'Processing summarize job placeholder');
    // Placeholder: In Week 5 this will call LLM summarization.
    // For orchestration in Week B, return predictable fields.
    const summaryId = `sum_${job.data.release_id}`;
    return { release_id: job.data.release_id, summary_id: summaryId, claim_batch: [], status: 'queued' };
  }
}
