# Monitoring Stack (Week 4)

## Prometheus
Example scrape config (`monitoring/prometheus.yml`):

```yaml
scrape_configs:
  - job_name: ingestion-api
    static_configs:
      - targets: ['ingestion-api:8000']
  - job_name: queue-worker
    static_configs:
      - targets: ['queue-worker:9100']
```

## Grafana Dashboard
Import `monitoring/grafana-dashboard.json` to visualize:
- Queue job rates (`queue_job_results_total`)
- Queue depth (`queue_depth_total`)
- Ingestion metrics (`beeline_ingestion_runs_total`, etc.)
- Cost trends (via `/costs` API panel + Prometheus `cost:hour` counters via `redis_exporter`).

## Alerts
Sample alert rules (`monitoring/alerts.yml`):
- `CostBreakerOpen`: fires when `queue_job_results_total{status="failed"}` spikes alongside `/costs` threshold.
- `QueueBacklogHigh`: backlog >100 for >5 minutes.
- `JobFailureRateHigh`: >5% failures in 10m.

Configure Alertmanager to route `severity=critical` to Slack/email; info/warn go to a low-noise channel.
Circuit breaker openings also publish `breaker_open:*` messages on Redis (`alerts` channel); route
those via `redis-stream-exporter` or a lightweight subscriber that forwards to Slack.
