 import { Queue, QueueEvents, JobsOptions } from 'bullmq';
import { AppConfig, QueueName } from './config';
import { createRedisOptions } from './redis';

export interface QueueFactoryOptions {
  queueName: QueueName;
  config: AppConfig;
}

export function createQueue({ queueName, config }: QueueFactoryOptions): Queue {
  const connection = createRedisOptions(config);
  return new Queue(queueName, {
    connection,
    defaultJobOptions: defaultJobOptions(config)
  });
}

export function createQueueEvents(queueName: QueueName, config: AppConfig): QueueEvents {
  return new QueueEvents(queueName, { connection: createRedisOptions(config) });
}

export function defaultJobOptions(config: AppConfig): JobsOptions {
  return {
    attempts: config.defaultAttempts,
    removeOnComplete: true,
    removeOnFail: false,
    backoff: {
      type: 'exponential',
      delay: config.backoffInitialMs
    }
  };
}
