import { Job } from 'bullmq';
import { BaseWorker } from './baseWorker';
import { VerifyJobPayload } from '../queues/payloads';

interface VerifyResult {
  status: string;
  verdicts?: Array<{ claim_id: string; verdict: string; confidence: number }>;
}

export class VerifyWorker extends BaseWorker<VerifyJobPayload, VerifyResult> {
  protected async process(
    job: Job<VerifyJobPayload>,
    _runId: number
  ): Promise<VerifyResult> {
    const { summary_id, claim_batch, release_id } = job.data;
    const url = `${this.config.pythonApiUrl}/internal/process/verify`;

    this.logger.info({ jobId: job.id, releaseId: release_id, summaryId: summary_id }, 'Calling Python verify endpoint');

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summary_id, claim_batch, release_id }),
      signal: AbortSignal.timeout(120_000),
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Verify API returned ${response.status}: ${body}`);
    }

    const result = await response.json() as VerifyResult;
    this.logger.info({ jobId: job.id, releaseId: release_id, status: result.status }, 'Verify complete');
    return result;
  }
}
