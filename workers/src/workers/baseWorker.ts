import { Job, Worker } from 'bullmq';
import pino from 'pino';
import { AppConfig, QueueName } from '../config';
import { createRedisOptions } from '../redis';
import { JobStore, JobRunMetadata } from '../stores/jobStore';
import { recordJobFailure, recordJobSuccess } from '../metrics/registry';

export abstract class BaseWorker<TPayload extends Record<string, unknown>, TResult = unknown> {
  protected readonly queueName: QueueName;
  protected readonly config: AppConfig;
  protected readonly logger = pino({ name: 'worker' });
  protected worker?: Worker<TPayload, TResult>;
  protected readonly jobStore: JobStore;

  constructor(queueName: QueueName, config: AppConfig) {
    this.queueName = queueName;
    this.config = config;
    this.jobStore = new JobStore(config.dbUrl);
  }

  async start(): Promise<void> {
    this.worker = new Worker<TPayload, TResult>(this.queueName, this.processWrapper.bind(this), {
      connection: createRedisOptions(this.config),
      concurrency: this.config.concurrency
    });

    this.worker.on('completed', (job) => {
      this.logger.info({ queue: this.queueName, jobId: job.id }, 'Job completed');
    });

    this.worker.on('failed', (job, err) => {
      this.logger.error({ queue: this.queueName, jobId: job?.id, err }, 'Job failed');
    });

    process.once('SIGINT', () => this.stop());
    process.once('SIGTERM', () => this.stop());

    this.logger.info({ queue: this.queueName }, 'Worker started');
  }

  private async processWrapper(job: Job<TPayload, TResult>): Promise<TResult> {
    const metadata = this.buildMetadata(job);
    const runId = await this.jobStore.recordRunStart(this.queueName, job.data, metadata);
    const started = Date.now();
    try {
      const result = await this.process(job, runId);
      const duration = Date.now() - started;
      await this.jobStore.recordRunSuccess(runId, result, duration);
      recordJobSuccess(this.queueName, duration);
      return result;
    } catch (error) {
      const duration = Date.now() - started;
      await this.jobStore.recordRunFailure(
        runId,
        this.queueName,
        job.data,
        error as Error,
        job.attemptsMade ?? 1,
        job.opts.attempts ?? this.config.defaultAttempts,
        duration,
        { ...metadata, bullmqJobId: job.id?.toString() }
      );
      recordJobFailure(this.queueName);
      throw error;
    }
  }

  protected abstract process(job: Job<TPayload, TResult>, runId: number): Promise<TResult>;

  private buildMetadata(job: Job<TPayload, TResult>): JobRunMetadata {
    const payload = (job.data || {}) as Record<string, unknown>;
    const releaseId = this.extractFirstString(payload, ['release_id', 'releaseId']);
    const articleId = this.extractFirstString(payload, ['article_id', 'articleId']);
    const priorityValue = payload.priority;
    return {
      stage: this.queueName,
      releaseId,
      articleId,
      priority: typeof priorityValue === 'number' ? priorityValue : undefined
    };
  }

  private extractFirstString(payload: Record<string, unknown>, keys: string[]): string | undefined {
    for (const key of keys) {
      const value = payload[key];
      if (typeof value === 'string' && value.length > 0) {
        return value;
      }
    }
    return undefined;
  }

  async stop(): Promise<void> {
    this.logger.info({ queue: this.queueName }, 'Stopping worker');
    await this.worker?.close();
    await this.jobStore.close();
  }
}
