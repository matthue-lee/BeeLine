import { loadConfig } from '../config';
import { createQueue } from '../queues';

async function main() {
  const config = loadConfig();
  const queue = createQueue({ queueName: 'ingest', config });
  const total = Number(process.argv[2] ?? '25');
  const jobs = Array.from({ length: total }).map((_, idx) => ({
    name: `ingest-${idx}`,
    data: {
      feed_url: 'synthetic://demo',
      source_id: `demo-${idx}`,
      triggered_by: 'manual'
    }
  }));
  await queue.addBulk(jobs);
  console.log(`Enqueued ${jobs.length} ingest jobs`);
  await queue.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
