import express from 'express';
import { register } from './registry';

export function startMetricsServer(port: number): void {
  const app = express();
  app.get('/health', (_req, res) => res.json({ status: 'ok' }));
  app.get('/metrics', async (_req, res) => {
    res.set('Content-Type', register.contentType);
    res.send(await register.metrics());
  });
  app.listen(port, () => {
    console.log(`Metrics server listening on ${port}`);
  });
}
