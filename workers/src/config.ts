import dotenv from 'dotenv';

dotenv.config();

export type QueueName =
  | 'ingest'
  | 'summarize'
  | 'verify'
  | 'embed'
  | 'link'
  | 'entity_extract';

export const QUEUE_NAMES: QueueName[] = [
  'ingest',
  'summarize',
  'verify',
  'embed',
  'link',
  'entity_extract'
];

export interface AppConfig {
  redisUrl: string;
  redisTls: boolean;
  redisKeyPrefix: string;
  dbUrl: string;
  workerName: string;
  concurrency: number;
  metricsPort: number;
  defaultAttempts: number;
  backoffInitialMs: number;
  backoffMultiplier: number;
}

export function loadConfig(): AppConfig {
  const redisTls = process.env.REDIS_TLS === '1';
  const metricsPort = parseInt(process.env.WORKER_METRICS_PORT ?? '9100', 10);
  return {
    redisUrl: process.env.REDIS_URL ?? 'redis://localhost:6379',
    redisTls,
    redisKeyPrefix: process.env.REDIS_QUEUE_PREFIX ?? 'beeline',
    dbUrl: process.env.DATABASE_URL ?? 'postgresql://beeline:beeline@localhost:5432/beeline',
    workerName: process.env.WORKER_NAME ?? 'beeline-worker',
    concurrency: parseInt(process.env.WORKER_CONCURRENCY ?? '5', 10),
    metricsPort,
    defaultAttempts: parseInt(process.env.WORKER_MAX_ATTEMPTS ?? '3', 10),
    backoffInitialMs: parseInt(process.env.WORKER_BACKOFF_INITIAL_MS ?? '1000', 10),
    backoffMultiplier: parseInt(process.env.WORKER_BACKOFF_MULTIPLIER ?? '2', 10)
  };
}
