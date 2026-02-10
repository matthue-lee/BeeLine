import { Pool } from 'pg';

export interface JobPayload {
  [key: string]: unknown;
}

export class JobStore {
  private pool: Pool;

  constructor(dbUrl: string) {
    this.pool = new Pool({ connectionString: dbUrl });
  }

  async recordRunStart(jobType: string, payload: JobPayload): Promise<number> {
    const result = await this.pool.query(
      `INSERT INTO job_runs (job_type, status, params, started_at)
       VALUES ($1, 'running', $2, NOW())
       RETURNING id`,
      [jobType, payload]
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
    durationMs: number
  ): Promise<void> {
    await this.pool.query(
      `UPDATE job_runs SET status='failed', error_message=$1, finished_at=NOW(), duration_ms=$2
       WHERE id=$3`,
      [error.message, durationMs, runId]
    );

    if (attemptsMade >= maxAttempts) {
      await this.pool.query(
        `INSERT INTO failed_jobs (job_run_id, job_type, payload, error_message, retry_count, max_retries, failed_at)
         VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
        [runId, jobType, payload, error.message, attemptsMade, maxAttempts]
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
