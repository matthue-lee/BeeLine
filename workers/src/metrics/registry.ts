import client from 'prom-client';

const register = new client.Registry();
client.collectDefaultMetrics({ register });

const jobDuration = new client.Histogram({
  name: 'queue_job_duration_seconds',
  help: 'Duration of processed jobs',
  labelNames: ['queue'],
  registers: [register]
});

const jobResultCounter = new client.Counter({
  name: 'queue_job_results_total',
  help: 'Completed jobs labeled by status',
  labelNames: ['queue', 'status'],
  registers: [register]
});

const queueDepthGauge = new client.Gauge({
  name: 'queue_depth_total',
  help: 'BullMQ queue depth by status',
  labelNames: ['queue', 'state'],
  registers: [register]
});

export function recordJobSuccess(queue: string, durationMs: number) {
  jobResultCounter.labels(queue, 'completed').inc();
  jobDuration.labels(queue).observe(durationMs / 1000);
}

export function recordJobFailure(queue: string) {
  jobResultCounter.labels(queue, 'failed').inc();
}

export function setQueueDepth(queue: string, counts: { waiting: number; active: number; delayed: number }) {
  queueDepthGauge.labels(queue, 'waiting').set(counts.waiting);
  queueDepthGauge.labels(queue, 'active').set(counts.active);
  queueDepthGauge.labels(queue, 'delayed').set(counts.delayed);
}

export { register };
