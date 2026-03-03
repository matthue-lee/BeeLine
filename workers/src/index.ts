import { loadConfig, QueueName } from './config';
import { IngestWorker } from './workers/ingestWorker';
import { SummarizeWorker } from './workers/summarizeWorker';
import { VerifyWorker } from './workers/verifyWorker';
import { EmbedWorker } from './workers/embedWorker';
import { LinkWorker } from './workers/linkWorker';
import { EntityExtractWorker } from './workers/entityExtractWorker';
import { startOrchestrator } from './orchestration/JobOrchestrator';
import { startMetricsServer } from './metrics/server';
import { createQueue } from './queues';
import { setQueueDepth } from './metrics/registry';

const config = loadConfig();
const queueName = (process.env.WORKER_QUEUE as QueueName) || 'ingest';

async function bootstrap(): Promise<void> {
  startMetricsServer(config.metricsPort);
  if (process.env.START_ORCHESTRATOR === '1' || process.env.WORKER_QUEUE === 'orchestrator') {
    startOrchestrator();
  }
  const queue = createQueue({ queueName, config });
  setInterval(async () => {
    const counts = await queue.getJobCounts('waiting', 'active', 'delayed');
    setQueueDepth(queueName, {
      waiting: counts.waiting,
      active: counts.active,
      delayed: counts.delayed
    });
  }, 5000);
  switch (queueName) {
    case 'ingest':
      await new IngestWorker(queueName, config).start();
      break;
    case 'summarize':
      await new SummarizeWorker(queueName, config).start();
      break;
    case 'verify':
      await new VerifyWorker(queueName, config).start();
      break;
    case 'embed':
      await new EmbedWorker(queueName, config).start();
      break;
    case 'link':
      await new LinkWorker(queueName, config).start();
      break;
    case 'entity_extract':
      await new EntityExtractWorker(queueName, config).start();
      break;
    default:
      throw new Error(`Queue ${queueName} not yet implemented`);
  }
}

bootstrap().catch((err) => {
  console.error('Failed to start worker', err);
  process.exit(1);
});
