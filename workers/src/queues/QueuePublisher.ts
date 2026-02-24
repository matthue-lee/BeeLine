import { Queue, JobsOptions, QueueOptions, ConnectionOptions } from 'bullmq';

import type {
  SummarizeJobPayload,
  VerifyJobPayload,
  EmbedJobPayload,
  LinkJobPayload,
  EntityExtractJobPayload
} from './payloads';

type StageName = 'summarize' | 'verify' | 'embed' | 'link' | 'entity_extract';

const DEFAULT_CONNECTION: ConnectionOptions = {
  host: process.env.REDIS_HOST || '127.0.0.1',
  port: Number(process.env.REDIS_PORT || '6379'),
  password: process.env.REDIS_PASSWORD || undefined
};

const STAGE_JOB_OPTIONS: Record<StageName, JobsOptions> = {
  summarize: { attempts: 3, backoff: { type: 'exponential', delay: 5000 } },
  verify: { attempts: 3, backoff: { type: 'exponential', delay: 5000 } },
  embed: { attempts: 5, backoff: { type: 'exponential', delay: 2000 } },
  link: { attempts: 4, backoff: { type: 'exponential', delay: 3000 } },
  entity_extract: { attempts: 4, backoff: { type: 'exponential', delay: 3000 } }
};

type QueueFactory = (name: StageName, opts: QueueOptions) => Queue;

export class QueuePublisher {
  private readonly summarizeQueue: Queue;
  private readonly verifyQueue: Queue;
  private readonly embedQueue: Queue;
  private readonly linkQueue: Queue;
  private readonly entityQueue: Queue;

  constructor(
    connection: ConnectionOptions = DEFAULT_CONNECTION,
    queueFactory: QueueFactory = (name, opts) => new Queue(name, opts)
  ) {
    const options: QueueOptions = { connection };
    this.summarizeQueue = queueFactory('summarize', options);
    this.verifyQueue = queueFactory('verify', options);
    this.embedQueue = queueFactory('embed', options);
    this.linkQueue = queueFactory('link', options);
    this.entityQueue = queueFactory('entity_extract', options);
  }

  enqueueSummarize(payload: SummarizeJobPayload, opts?: JobsOptions) {
    return this.enqueue(this.summarizeQueue, 'summarize', payload.idempotency_token, payload, payload.priority, opts);
  }

  enqueueVerify(payload: VerifyJobPayload, opts?: JobsOptions) {
    return this.enqueue(this.verifyQueue, 'verify', payload.idempotency_token, payload, undefined, opts);
  }

  enqueueEmbed(payload: EmbedJobPayload, opts?: JobsOptions) {
    return this.enqueue(this.embedQueue, 'embed', payload.idempotency_token, payload, undefined, opts);
  }

  enqueueLink(payload: LinkJobPayload, opts?: JobsOptions) {
    return this.enqueue(this.linkQueue, 'link', payload.idempotency_token, payload, undefined, opts);
  }

  enqueueEntityExtract(payload: EntityExtractJobPayload, opts?: JobsOptions) {
    return this.enqueue(this.entityQueue, 'entity_extract', payload.idempotency_token, payload, undefined, opts);
  }

  private enqueue(
    queue: Queue,
    stage: StageName,
    idempotencyToken: string,
    payload: Record<string, unknown> | unknown,
    priority?: number,
    opts?: JobsOptions
  ) {
    const base = STAGE_JOB_OPTIONS[stage];
    const tags = [
      `stage:${stage}`,
      `priority:${priority ?? 0}`
    ];
    const finalOptions: JobsOptions = {
      ...base,
      ...opts,
      jobId: idempotencyToken,
      priority
    };
    (finalOptions as Record<string, unknown>)['tags'] = tags;
    return queue.add(stage, payload as Record<string, unknown>, finalOptions);
  }
}

export const queuePublisher = new QueuePublisher();
