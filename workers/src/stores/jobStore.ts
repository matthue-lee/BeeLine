import { Pool } from 'pg';

export interface JobPayload {
  [key: string]: unknown;
}

export interface JobRunMetadata {
  stage?: string;
  releaseId?: string;
  articleId?: string;
  priority?: number;
  triggerJobId?: number | null;
}

export interface JobRunFailureMetadata extends JobRunMetadata {
  bullmqJobId?: string;
}

export class JobStore {
  private pool: Pool;

  constructor(dbUrl: string) {
    this.pool = new Pool({ connectionString: dbUrl });
  }

  async recordRunStart(
    jobType: string,
    payload: JobPayload,
    metadata: JobRunMetadata = {}
  ): Promise<number> {
    const { stage, releaseId, articleId, priority = 0, triggerJobId } = metadata;
    const result = await this.pool.query(
      `INSERT INTO job_runs (job_type, stage, release_id, article_id, priority, trigger_job_id, status, params, started_at)
       VALUES ($1, $2, $3, $4, $5, $6, 'running', $7, NOW())
       RETURNING id`,
      [jobType, stage, releaseId, articleId, priority, triggerJobId, payload]
    );
    return result.rows[0].id as number;
  }

  async recordRunSuccess(runId: number, resultPayload: unknown, durationMs: number): Promise<void> {
    await this.pool.query(
      `UPDATE job_runs SET status='completed', result=$1, finished_at=NOW(), duration_ms=$2
       WHERE id=$3`,
      [resultPayload, durationMs, runId]
    );
  }

  async recordRunFailure(
    runId: number,
    jobType: string,
    payload: JobPayload,
    error: Error,
    attemptsMade: number,
    maxAttempts: number,
    durationMs: number,
    metadata: JobRunFailureMetadata = {}
  ): Promise<void> {
    const { stage, releaseId, bullmqJobId } = metadata;
    await this.pool.query(
      `UPDATE job_runs SET status='failed', error_message=$1, finished_at=NOW(), duration_ms=$2
       WHERE id=$3`,
      [error.message, durationMs, runId]
    );

    if (attemptsMade >= maxAttempts) {
      await this.pool.query(
        `INSERT INTO failed_jobs (job_run_id, job_type, stage, release_id, payload, payload_snapshot, error_message, retry_count, max_retries, bullmq_job_id, failed_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())`,
        [
          runId,
          jobType,
          stage,
          releaseId,
          payload,
          payload,
          error.message,
          attemptsMade,
          maxAttempts,
          bullmqJobId
        ]
      );
    }
  }

  async listRecent(limit = 50) {
    const result = await this.pool.query(
      `SELECT id, job_type, status, started_at, finished_at, duration_ms
       FROM job_runs
       ORDER BY started_at DESC
       LIMIT $1`,
      [limit]
    );
    return result.rows;
  }

  async fetchFailedJobs(limit = 25) {
    const result = await this.pool.query(
      `SELECT id, job_type, payload, retry_count, max_retries
       FROM failed_jobs
       ORDER BY failed_at ASC
       LIMIT $1`,
      [limit]
    );
    return result.rows;
  }

  async removeFailedJob(id: number): Promise<void> {
    await this.pool.query(`DELETE FROM failed_jobs WHERE id=$1`, [id]);
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}
