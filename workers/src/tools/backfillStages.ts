/* Backfill stages for existing releases. */
import { Pool } from 'pg';
import { queuePublisher } from '../queues/QueuePublisher';
import {
  makeEntityExtractIdempotencyToken,
  makeEmbedIdempotencyToken,
  makeSummarizeIdempotencyToken
} from '../queues/tokens';

type Stage = 'summarize' | 'embed' | 'entity_extract';

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const stage = (args.stage as Stage) || (args.s as Stage);
  if (!stage || !['summarize', 'embed', 'entity_extract'].includes(stage)) {
    throw new Error("--stage must be one of 'summarize','embed','entity_extract'");
  }
  const days = Number(args.days ?? args.d ?? 90);
  const dryRun = Boolean(args['dry-run'] ?? args.n ?? false);

  const dbUrl = process.env.DATABASE_URL || 'postgresql://beeline:beeline@localhost:5432/beeline';
  const pool = new Pool({ connectionString: dbUrl });

  const releases = await pool.query(
    `SELECT id, text_clean, text_raw FROM releases
     WHERE ${stage}_status = 'pending' AND created_at > NOW() - INTERVAL '${days} days'
     ORDER BY created_at DESC`
  );

  let enqueued = 0;
  let skipped = 0;
  for (const row of releases.rows) {
    const id: string = row.id;
    const text: string = row.text_clean || row.text_raw || '';
    if (!text.trim()) {
      skipped += 1;
      continue;
    }
    if (dryRun) {
      skipped += 1;
      continue;
    }
    if (stage === 'summarize') {
      await queuePublisher.enqueueSummarize({ release_id: id, idempotency_token: makeSummarizeIdempotencyToken(id) });
    } else if (stage === 'embed') {
      const crypto = await import('crypto');
      const textHash = crypto.createHash('sha256').update(text).digest('hex');
      await queuePublisher.enqueueEmbed({
        source_type: 'release',
        source_id: id,
        text_hash: textHash,
        idempotency_token: makeEmbedIdempotencyToken('release', id, textHash)
      });
    } else if (stage === 'entity_extract') {
      await queuePublisher.enqueueEntityExtract({
        source_type: 'release',
        source_id: id,
        idempotency_token: makeEntityExtractIdempotencyToken('release', id)
      });
    }
    await pool.query(`UPDATE releases SET ${stage}_status='queued' WHERE id = $1`, [id]);
    enqueued += 1;
  }
  // eslint-disable-next-line no-console
  console.log(`Backfill complete: enqueued=${enqueued}, skipped=${skipped}`);
  await pool.end();
}

function parseArgs(argv: string[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const val = argv[i + 1] && !argv[i + 1].startsWith('-') ? argv[++i] : true;
      out[key] = val;
    } else if (a.startsWith('-')) {
      const key = a.slice(1);
      const val = argv[i + 1] && !argv[i + 1].startsWith('-') ? argv[++i] : true;
      out[key] = val;
    }
  }
  return out;
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});
