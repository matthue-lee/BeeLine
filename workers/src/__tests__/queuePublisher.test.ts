import assert from 'node:assert/strict';

import { Queue, JobsOptions } from 'bullmq';
import { QueuePublisher } from '../queues/QueuePublisher';
import type { SummarizeJobPayload, EmbedJobPayload } from '../queues/payloads';

class FakeQueue implements Pick<Queue, 'add'> {
  public lastJob?: { name: string; payload: unknown; opts?: JobsOptions };

  async add(name: string, payload: unknown, opts?: JobsOptions) {
    this.lastJob = { name, payload, opts };
    return { id: opts?.jobId } as unknown as ReturnType<Queue['add']>;
  }
}

function createPublisher() {
  const queues: Record<string, FakeQueue> = {};
  const factory = (name: any) => {
    const queue = new FakeQueue();
    queues[name] = queue;
    return queue as unknown as Queue;
  };
  const publisher = new QueuePublisher(undefined, factory);
  return { publisher, queues };
}

(async () => {
  const { publisher, queues } = createPublisher();
  const payload: SummarizeJobPayload = {
    release_id: 'rel-1',
    idempotency_token: 'tok-1',
    priority: 2
  };
  await publisher.enqueueSummarize(payload);
  const recorded = queues.summarize.lastJob;
  assert(recorded, 'summarize queue should record job');
  assert.equal(recorded?.name, 'summarize');
  assert.equal(recorded?.opts?.jobId, 'tok-1');
  assert.equal(recorded?.opts?.priority, 2);
  const recordedOpts = recorded?.opts as Record<string, unknown> | undefined;
  assert(recordedOpts?.['tags'] && Array.isArray(recordedOpts['tags']));
  assert((recordedOpts?.['tags'] as string[]).includes('stage:summarize'));

  const embedPayload: EmbedJobPayload = {
    source_type: 'release',
    source_id: 'rel-1',
    text_hash: 'abc',
    idempotency_token: 'tok-embed'
  };
  await publisher.enqueueEmbed(embedPayload);
  const embedRecorded = queues.embed.lastJob;
  assert(embedRecorded, 'embed queue should record job');
  assert.equal(embedRecorded?.opts?.jobId, 'tok-embed');
  const embedOpts = embedRecorded?.opts as Record<string, unknown> | undefined;
  assert(embedOpts?.['tags'] && Array.isArray(embedOpts['tags']));
  assert((embedOpts?.['tags'] as string[]).includes('stage:embed'));

  console.log('QueuePublisher tests passed');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
