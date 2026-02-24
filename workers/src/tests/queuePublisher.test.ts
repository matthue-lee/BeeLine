import assert from 'assert';
import type { JobsOptions, Queue, QueueOptions, ConnectionOptions } from 'bullmq';
import { QueuePublisher } from '../queues/QueuePublisher';

type StageName = 'summarize' | 'verify' | 'embed' | 'link' | 'entity_extract';

class FakeQueue implements Partial<Queue> {
  public last: { name?: string; data?: unknown; opts?: JobsOptions } = {};
  constructor(public readonly qname: string) {}
  async add(name: string, data: Record<string, unknown>, opts?: JobsOptions) {
    this.last = { name, data, opts };
    // Simulate BullMQ Job shape minimally
    return { id: (opts?.jobId ?? 'noid').toString(), name, data, opts } as unknown as any;
  }
}

function makePublisher() {
  const queues: Record<StageName, FakeQueue> = {
    summarize: new FakeQueue('summarize'),
    verify: new FakeQueue('verify'),
    embed: new FakeQueue('embed'),
    link: new FakeQueue('link'),
    entity_extract: new FakeQueue('entity_extract')
  };
  const factory = (name: StageName, _opts: QueueOptions) => queues[name] as unknown as Queue;
  const conn: ConnectionOptions = { host: '127.0.0.1', port: 6379 };
  const pub = new QueuePublisher(conn, factory);
  return { pub, queues };
}

async function testSummarizeEnqueue() {
  const { pub, queues } = makePublisher();
  const payload = { release_id: 'r1', idempotency_token: 'tok-123', priority: 2 };
  const job = await pub.enqueueSummarize(payload);
  const last = queues.summarize.last;
  assert.strictEqual(last.name, 'summarize', 'uses correct job name');
  assert.strictEqual(job.id, 'tok-123', 'jobId equals idempotency_token');
  assert.strictEqual(last.opts?.jobId, 'tok-123');
  assert.strictEqual(last.opts?.attempts, 3);
  assert.deepStrictEqual(last.opts?.backoff, { type: 'exponential', delay: 5000 });
  assert.strictEqual(last.opts?.priority, 2);
  const tags = (last.opts as any)?.tags as string[] | undefined;
  assert.ok(tags && tags.includes('stage:summarize') && tags.includes('priority:2'), 'tags include stage and priority');
}

async function testEmbedEnqueuePolicy() {
  const { pub, queues } = makePublisher();
  await pub.enqueueEmbed({ source_type: 'release', source_id: 'r2', text_hash: 'h', idempotency_token: 'tok-emb' });
  const last = queues.embed.last;
  assert.strictEqual(last.name, 'embed');
  assert.strictEqual(last.opts?.attempts, 5);
  assert.deepStrictEqual(last.opts?.backoff, { type: 'exponential', delay: 2000 });
}

async function testVerifyEnqueuePolicy() {
  const { pub, queues } = makePublisher();
  await pub.enqueueVerify({ summary_id: 's1', release_id: 'r1', claim_batch: ['a'], idempotency_token: 'tok-v' });
  const last = queues.verify.last;
  assert.strictEqual(last.name, 'verify');
  assert.strictEqual(last.opts?.attempts, 3);
  assert.deepStrictEqual(last.opts?.backoff, { type: 'exponential', delay: 5000 });
}

async function run() {
  await testSummarizeEnqueue();
  await testEmbedEnqueuePolicy();
  await testVerifyEnqueuePolicy();
  // eslint-disable-next-line no-console
  console.log('QueuePublisher tests passed');
}

run().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});

