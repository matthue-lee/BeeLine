import { loadConfig, QueueName } from '../config';
import { createQueue } from '../queues';
import { JobStore } from '../stores/jobStore';

async function main() {
  const config = loadConfig();
  const limit = Number(process.argv[2] ?? '20');
  const store = new JobStore(config.dbUrl);
  const failedJobs = await store.fetchFailedJobs(limit);
  if (failedJobs.length === 0) {
    console.log('No failed jobs to replay');
    await store.close();
    return;
  }
  for (const job of failedJobs) {
    const queueName = job.job_type as QueueName;
    const queue = createQueue({ queueName, config });
    await queue.add(`${queueName}-replay-${job.id}`, job.payload);
    await queue.close();
    await store.removeFailedJob(job.id);
    console.log(`Replayed job ${job.id} onto ${queueName}`);
  }
  await store.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
