import { Job } from 'bullmq';
import { BaseWorker } from './baseWorker';
import { EntityExtractJobPayload } from '../queues/payloads';

interface EntityExtractResult {
  status: string;
  entity_count: number;
}

export class EntityExtractWorker extends BaseWorker<EntityExtractJobPayload, EntityExtractResult> {
  protected async process(
    job: Job<EntityExtractJobPayload>,
    _runId: number
  ): Promise<EntityExtractResult> {
    const { source_type, source_id } = job.data;
    const url = `${this.config.pythonApiUrl}/internal/process/entity_extract`;

    this.logger.info({ jobId: job.id, sourceType: source_type, sourceId: source_id }, 'Calling Python entity_extract endpoint');

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_type, source_id }),
      signal: AbortSignal.timeout(120_000),
    });

    if (!response.ok) {
      const body = await response.text();
      // 503 means entity extraction is disabled on this instance — treat as success
      if (response.status === 503) {
        this.logger.warn({ jobId: job.id }, 'Entity extraction disabled on Python instance; skipping');
        return { status: 'skipped', entity_count: 0 };
      }
      throw new Error(`Entity extract API returned ${response.status}: ${body}`);
    }

    const result = await response.json() as EntityExtractResult;
    this.logger.info({ jobId: job.id, sourceType: source_type, sourceId: source_id, entityCount: result.entity_count }, 'Entity extract complete');
    return result;
  }
}
