/**
 * Replay failed jobs from the failed_jobs table back onto their BullMQ queues.
 *
 * Usage:
 *   npx ts-node src/tools/replayFailed.ts [--limit N] [--stage STAGE] [--dry-run]
 *
 * Options:
 *   --limit N      Max jobs to replay (default 20)
 *   --stage STAGE  Only replay jobs for a specific stage (summarize|verify|embed|link|entity_extract)
 *   --dry-run      Print jobs that would be replayed without actually requeueing
 */
import { loadConfig, QueueName } from '../config';
import { createQueue } from '../queues';
import { JobStore } from '../stores/jobStore';

function parseArgs(argv: string[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const val = argv[i + 1] && !argv[i + 1].startsWith('-') ? argv[++i] : true;
      out[key] = val;
    }
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const limit = Number(args.limit ?? 20);
  const stageFilter = typeof args.stage === 'string' ? args.stage : undefined;
  const dryRun = Boolean(args['dry-run']);

  const config = loadConfig();
  const store = new JobStore(config.dbUrl);
  const failedJobs = await store.fetchFailedJobs(limit, stageFilter);

  if (failedJobs.length === 0) {
    console.log(stageFilter
      ? `No failed jobs for stage '${stageFilter}'`
      : 'No failed jobs to replay');
    await store.close();
    return;
  }

  console.log(`Found ${failedJobs.length} failed job(s)${stageFilter ? ` [stage=${stageFilter}]` : ''}${dryRun ? ' (dry-run)' : ''}:`);
  console.log('─'.repeat(60));

  for (const job of failedJobs) {
    const queueName = (job.stage ?? job.job_type) as QueueName;
    console.log(`  id=${job.id}  stage=${job.stage ?? '—'}  release_id=${job.release_id ?? '—'}`);
    console.log(`  error: ${job.error_message ?? '—'}`);
    console.log(`  payload: ${JSON.stringify(job.payload)}`);

    if (!dryRun) {
      const queue = createQueue({ queueName, config });
      await queue.add(`${queueName}-replay-${job.id}`, job.payload);
      await queue.close();
      await store.removeFailedJob(job.id);
      console.log(`  → Replayed onto queue '${queueName}' and removed from failed_jobs`);
    } else {
      console.log(`  → [dry-run] Would replay onto queue '${queueName}'`);
    }
    console.log('─'.repeat(60));
  }

  if (dryRun) {
    console.log(`Dry run complete. Re-run without --dry-run to replay.`);
  } else {
    console.log(`Replayed ${failedJobs.length} job(s).`);
  }

  await store.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
