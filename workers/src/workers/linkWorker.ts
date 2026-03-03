import { Job } from 'bullmq';
import { BaseWorker } from './baseWorker';
import { LinkJobPayload } from '../queues/payloads';

interface LinkResult {
  status: string;
}

export class LinkWorker extends BaseWorker<LinkJobPayload, LinkResult> {
  protected async process(
    job: Job<LinkJobPayload>,
    _runId: number
  ): Promise<LinkResult> {
    const { release_id, candidate_article_ids } = job.data;
    const url = `${this.config.pythonApiUrl}/internal/process/link`;

    this.logger.info({ jobId: job.id, releaseId: release_id }, 'Calling Python link endpoint');

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ release_id, candidate_article_ids }),
      signal: AbortSignal.timeout(60_000),
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Link API returned ${response.status}: ${body}`);
    }

    const result = await response.json() as LinkResult;
    this.logger.info({ jobId: job.id, releaseId: release_id }, 'Link complete');
    return result;
  }
}
