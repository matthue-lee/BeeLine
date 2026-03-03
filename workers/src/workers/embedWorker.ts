import { Job } from 'bullmq';
import { BaseWorker } from './baseWorker';
import { EmbedJobPayload } from '../queues/payloads';

interface EmbedResult {
  source_type: string;
  source_id: string;
  release_id: string | null;
  text_hash: string | null;
  candidate_article_ids: string[];
  status: string;
}

export class EmbedWorker extends BaseWorker<EmbedJobPayload, EmbedResult> {
  protected async process(
    job: Job<EmbedJobPayload>,
    _runId: number
  ): Promise<EmbedResult> {
    const { source_type, source_id } = job.data;
    const url = `${this.config.pythonApiUrl}/internal/process/embed`;

    this.logger.info({ jobId: job.id, sourceType: source_type, sourceId: source_id }, 'Calling Python embed endpoint');

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_type, source_id }),
      signal: AbortSignal.timeout(60_000),
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Embed API returned ${response.status}: ${body}`);
    }

    const result = await response.json() as EmbedResult;
    this.logger.info({ jobId: job.id, sourceType: source_type, sourceId: source_id }, 'Embed complete');
    return result;
  }
}
