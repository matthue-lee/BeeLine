/**
 * Backfill stage jobs for releases that haven't been processed yet.
 *
 * Usage:
 *   npx ts-node src/tools/backfillStages.ts --stage STAGE [--days N] [--dry-run]
 *
 * Stages:
 *   summarize     Releases where summary_status='pending'
 *   verify        Releases where verify_status='pending' and a summary exists
 *   embed         Releases where embed_status='pending'
 *   link          Releases where link_status='pending'
 *   entity_extract Releases where entity_status='pending'
 */
import { Pool } from 'pg';
import { queuePublisher } from '../queues/QueuePublisher';
import {
  makeEntityExtractIdempotencyToken,
  makeEmbedIdempotencyToken,
  makeLinkIdempotencyToken,
  makeSummarizeIdempotencyToken,
  makeVerifyIdempotencyToken,
} from '../queues/tokens';

type Stage = 'summarize' | 'verify' | 'embed' | 'link' | 'entity_extract';
const VALID_STAGES: Stage[] = ['summarize', 'verify', 'embed', 'link', 'entity_extract'];

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const stage = (args.stage as Stage) || (args.s as Stage);
  if (!stage || !VALID_STAGES.includes(stage)) {
    throw new Error(`--stage must be one of: ${VALID_STAGES.join(', ')}`);
  }
  const days = Number(args.days ?? args.d ?? 90);
  const dryRun = Boolean(args['dry-run'] ?? args.n ?? false);
  const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

  const dbUrl = process.env.DATABASE_URL || 'postgresql://beeline:beeline@localhost:5432/beeline';
  const pool = new Pool({ connectionString: dbUrl });

  let enqueued = 0;
  let skipped = 0;

  if (stage === 'summarize') {
    const releases = await pool.query(
      `SELECT id, text_clean, text_raw FROM releases
       WHERE summary_status = 'pending' AND created_at > $1
       ORDER BY created_at DESC`,
      [cutoff]
    );
    for (const row of releases.rows) {
      const id: string = row.id;
      const text: string = row.text_clean || row.text_raw || '';
      if (!text.trim()) { skipped++; continue; }
      if (!dryRun) {
        await queuePublisher.enqueueSummarize({ release_id: id, idempotency_token: makeSummarizeIdempotencyToken(id) });
        await pool.query(`UPDATE releases SET summary_status='queued' WHERE id = $1`, [id]);
      }
      dryRun ? skipped++ : enqueued++;
    }

  } else if (stage === 'verify') {
    const rows = await pool.query(
      `SELECT r.id AS release_id, s.id::text AS summary_id, s.claims
       FROM releases r
       JOIN summaries s ON s.release_id = r.id
       WHERE r.verify_status = 'pending' AND r.created_at > $1
       ORDER BY r.created_at DESC`,
      [cutoff]
    );
    for (const row of rows.rows) {
      const claimBatch: string[] = Array.isArray(row.claims)
        ? row.claims.map((c: { text?: string }) => c.text ?? '').filter(Boolean)
        : [];
      if (claimBatch.length === 0) { skipped++; continue; }
      if (!dryRun) {
        await queuePublisher.enqueueVerify({
          summary_id: row.summary_id,
          claim_batch: claimBatch,
          release_id: row.release_id,
          idempotency_token: makeVerifyIdempotencyToken(row.summary_id),
        });
        await pool.query(`UPDATE releases SET verify_status='queued' WHERE id = $1`, [row.release_id]);
      }
      dryRun ? skipped++ : enqueued++;
    }

  } else if (stage === 'embed') {
    const releases = await pool.query(
      `SELECT id, text_clean, text_raw FROM releases
       WHERE embed_status = 'pending' AND created_at > $1
       ORDER BY created_at DESC`,
      [cutoff]
    );
    for (const row of releases.rows) {
      const id: string = row.id;
      const text: string = row.text_clean || row.text_raw || '';
      if (!text.trim()) { skipped++; continue; }
      const { createHash } = await import('crypto');
      const textHash = createHash('sha256').update(text).digest('hex');
      if (!dryRun) {
        await queuePublisher.enqueueEmbed({
          source_type: 'release', source_id: id, text_hash: textHash,
          idempotency_token: makeEmbedIdempotencyToken('release', id, textHash),
        });
        await pool.query(`UPDATE releases SET embed_status='queued' WHERE id = $1`, [id]);
      }
      dryRun ? skipped++ : enqueued++;
    }

  } else if (stage === 'link') {
    const releases = await pool.query(
      `SELECT id FROM releases
       WHERE link_status = 'pending' AND created_at > $1
       ORDER BY created_at DESC`,
      [cutoff]
    );
    for (const row of releases.rows) {
      const id: string = row.id;
      if (!dryRun) {
        await queuePublisher.enqueueLink({
          release_id: id, candidate_article_ids: [],
          idempotency_token: makeLinkIdempotencyToken(id),
        });
        await pool.query(`UPDATE releases SET link_status='queued' WHERE id = $1`, [id]);
      }
      dryRun ? skipped++ : enqueued++;
    }

  } else if (stage === 'entity_extract') {
    const releases = await pool.query(
      `SELECT id, text_clean, text_raw FROM releases
       WHERE entity_status = 'pending' AND created_at > $1
       ORDER BY created_at DESC`,
      [cutoff]
    );
    for (const row of releases.rows) {
      const id: string = row.id;
      const text: string = row.text_clean || row.text_raw || '';
      if (!text.trim()) { skipped++; continue; }
      if (!dryRun) {
        await queuePublisher.enqueueEntityExtract({
          source_type: 'release', source_id: id,
          idempotency_token: makeEntityExtractIdempotencyToken('release', id),
        });
        await pool.query(`UPDATE releases SET entity_status='queued' WHERE id = $1`, [id]);
      }
      dryRun ? skipped++ : enqueued++;
    }
  }

  const label = dryRun ? 'Would enqueue' : 'Enqueued';
  console.log(`Backfill [${stage}]${dryRun ? ' (dry-run)' : ''}: ${label}=${enqueued}, skipped=${skipped}`);
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
  console.error(err);
  process.exit(1);
});
