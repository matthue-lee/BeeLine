import { Job } from 'bullmq';
import { BaseWorker } from './baseWorker';
import { SummarizeJobPayload } from '../queues/payloads';

interface SummarizeResult {
  release_id: string;
  summary_id: string | null;
  claim_batch: string[];
  status: string;
}

export class SummarizeWorker extends BaseWorker<SummarizeJobPayload, SummarizeResult> {
  protected async process(
    job: Job<SummarizeJobPayload>,
    _runId: number
  ): Promise<SummarizeResult> {
    const { release_id, prompt_version_hint } = job.data;
    const url = `${this.config.pythonApiUrl}/internal/process/summarize`;

    this.logger.info({ jobId: job.id, releaseId: release_id }, 'Calling Python summarize endpoint');

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ release_id, prompt_version_hint }),
      signal: AbortSignal.timeout(120_000),
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Summarize API returned ${response.status}: ${body}`);
    }

    const result = await response.json() as SummarizeResult;
    this.logger.info({ jobId: job.id, releaseId: release_id, summaryId: result.summary_id }, 'Summarize complete');
    return result;
  }
}
