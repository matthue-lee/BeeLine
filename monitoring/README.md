# Monitoring Stack

This folder ships starter configs/dashboards for observing the real app (HTTP API, ingestion
pipeline, summary generation, queue workers, and Alloy).

## Prometheus Scrapes

`monitoring/prometheus.yml` contains the base scrapes for `ingestion-api:8000`,
`queue-worker:9100`, and Redis/Node exporters. When running under Docker Compose, Prometheus or
Alloy should use container DNS names (`ingestion-api`, `queue-worker`, etc.) instead of `localhost`.

Key exported metrics:

| Metric | Description |
| --- | --- |
| `beeline_ingestion_runs_total{status}` | Count of ingestion jobs grouped by final status |
| `beeline_news_ingestion_runs_total{status}` | External news ingestion attempts grouped by status |
| `beeline_news_ingestion_run_seconds_bucket` | Histogram for news ingestion runtime |
| `beeline_news_articles_processed_total{result}` | Seen / inserted / updated article counters |
| `beeline_news_articles_pruned_total` | Articles removed by retention policy |
| `beeline_news_articles_total` | Gauge of articles available for cross-linking |
| `beeline_scheduler_job_runs_total{job,status}` | Scheduler job success/failure counts |
| `beeline_scheduler_job_seconds_bucket{job}` | Histogram for scheduler job runtimes |
| `beeline_scheduler_job_skips_total{job,reason}` | When jobs are skipped due to overlap/disabled |
| `beeline_scheduler_next_run_unixtime{job}` | Timestamp for the next scheduled fire per job |
| `beeline_rss_requests_total{feed,status}` | RSS HTTP calls + success/error rates |
| `beeline_summary_generations_total{status}` | Summaries attempted (success / cache hit / skipped / failed) |
| `beeline_summary_generation_seconds_bucket` | Histogram for LLM & persistence latency |
| `beeline_http_requests_total{method,endpoint,status}` | Application HTTP throughput |
| `beeline_http_request_seconds_bucket` | API latency histogram (use `histogram_quantile`) |

## Grafana Dashboard

Import `monitoring/grafana-dashboard.json` into Grafana. Panels included:

1. **Ingestion Run Rate** – `sum(rate(beeline_ingestion_runs_total[5m])) by (status)`
2. **Summary Outcomes** – `sum(rate(beeline_summary_generations_total[5m])) by (status)`
3. **Summary Latency** – `histogram_quantile(0.95, sum(rate(beeline_summary_generation_seconds_bucket[5m])) by (le))`
4. **API Throughput** – `sum(rate(beeline_http_requests_total[5m])) by (endpoint)`
5. **API P95 latency** – `histogram_quantile(0.95, sum(rate(beeline_http_request_seconds_bucket[5m])) by (le,endpoint))`
6. **RSS Errors** – `sum(rate(beeline_rss_requests_total{status!="200"}[15m])) by (status)`

These panels surface whether the ingestion job is stuck, summaries are failing, or the API SLA is
breached.

## Logs (Loki)

With Alloy forwarding `/var/log/alloy/alloy.log` and the ingestion API logs, typical queries:

```
{job="ingestion_api"} |~ "WARNING|ERROR"
{job="integrations/alloy", collector_id="<collector>"}
```

Use derived fields (request_id, release_id) to jump from Grafana Explore to Kibana/Sentry if needed.

## Alerts

`monitoring/alerts.yml` still provides queue-centric examples. Extend it with new metrics, e.g.:

- `SummaryFailuresSpike`: `sum(rate(beeline_summary_generations_total{status="failed"}[10m])) > 0`
- `ApiLatencyP95High`: `histogram_quantile(0.95, sum(rate(beeline_http_request_seconds_bucket[10m])) by (le)) > 1.0`

Route `severity=critical` alerts to Slack/email. Circuit breaker openings and cost breaches can be
handled by subscribing to the Redis `alerts` channel (`breaker_open:*`) or scraping the `/costs` endpoint.
