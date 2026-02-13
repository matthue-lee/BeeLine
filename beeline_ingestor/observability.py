"""Observability utilities (Sentry + Prometheus metrics)."""
from __future__ import annotations

import logging
import time
from typing import Optional

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sentry_sdk import capture_message, init as sentry_init
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)

REGISTRY = CollectorRegistry(auto_describe=True)

INGESTION_RUNS = Counter(
    "beeline_ingestion_runs_total",
    "Total ingestion runs partitioned by final status.",
    ("status",),
    registry=REGISTRY,
)

INGESTION_ITEMS = Counter(
    "beeline_ingested_documents_total",
    "Documents processed by ingestion grouped by result.",
    ("result",),
    registry=REGISTRY,
)

INGESTION_DURATION = Histogram(
    "beeline_ingestion_run_seconds",
    "Wall-clock duration of ingestion pipeline executions.",
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1200),
    registry=REGISTRY,
)

RELEASE_GAUGE = Gauge(
    "beeline_releases_total",
    "Current number of release documents stored in the database.",
    registry=REGISTRY,
)

LAST_SUCCESS_GAUGE = Gauge(
    "beeline_ingestion_last_success_unixtime",
    "Unix timestamp for the most recent successful ingestion run.",
    registry=REGISTRY,
)

SCHEDULER_JOB_RUNS = Counter(
    "beeline_scheduler_job_runs_total",
    "Scheduler job executions grouped by status.",
    ("job", "status"),
    registry=REGISTRY,
)

SCHEDULER_JOB_DURATION = Histogram(
    "beeline_scheduler_job_seconds",
    "Scheduler job execution latency.",
    ("job",),
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
    registry=REGISTRY,
)

SCHEDULER_JOB_SKIPS = Counter(
    "beeline_scheduler_job_skips_total",
    "Scheduler job invocations skipped due to overlap or disablement.",
    ("job", "reason"),
    registry=REGISTRY,
)

SCHEDULER_NEXT_RUN = Gauge(
    "beeline_scheduler_next_run_unixtime",
    "Unix timestamp for the next scheduled run per job.",
    ("job",),
    registry=REGISTRY,
)

SCHEDULER_JOB_ACTIVE = Gauge(
    "beeline_scheduler_job_running",
    "Whether the scheduler is actively executing a job (1/0).",
    ("job",),
    registry=REGISTRY,
)

RSS_REQUESTS = Counter(
    "beeline_rss_requests_total",
    "HTTP requests made to RSS feeds partitioned by status code.",
    ("feed", "status"),
    registry=REGISTRY,
)

RSS_REQUEST_DURATION = Histogram(
    "beeline_rss_request_seconds",
    "Latency for RSS HTTP fetch operations.",
    ("feed",),
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
    registry=REGISTRY,
)

SUMMARY_GENERATIONS = Counter(
    "beeline_summary_generations_total",
    "Summaries attempted grouped by status (success, skipped, failure).",
    ("status",),
    registry=REGISTRY,
)

SUMMARY_LATENCY = Histogram(
    "beeline_summary_generation_seconds",
    "LLM + persistence latency per summary generation.",
    buckets=(0.5, 1, 2, 5, 10, 20, 60),
    registry=REGISTRY,
)

CLAIM_VERIFICATIONS = Counter(
    "beeline_claim_verifications_total",
    "Verification verdicts grouped by outcome.",
    ("verdict",),
    registry=REGISTRY,
)

CLAIM_VERIFICATION_LATENCY = Histogram(
    "beeline_claim_verification_seconds",
    "Latency per claim verification.",
    buckets=(0.5, 1, 2, 5, 10, 20),
    registry=REGISTRY,
)

HTTP_REQUESTS = Counter(
    "beeline_http_requests_total",
    "HTTP requests served by the ingestion API grouped by method/endpoint/status.",
    ("method", "endpoint", "status"),
    registry=REGISTRY,
)

HTTP_LATENCY = Histogram(
    "beeline_http_request_seconds",
    "API request latency distribution.",
    ("method", "endpoint"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
    registry=REGISTRY,
)

_sentry_initialised = False


def init_sentry(
    dsn: Optional[str],
    *,
    environment: str,
    traces_sample_rate: float = 0.0,
    profiles_sample_rate: float = 0.0,
    enable_flask_integration: bool = False,
) -> bool:
    """Initialise Sentry if a DSN is provided."""

    global _sentry_initialised

    if _sentry_initialised or not dsn:
        return False

    integrations = [LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)]
    if enable_flask_integration:
        integrations.append(FlaskIntegration())

    sentry_init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        integrations=integrations,
        send_default_pii=False,
    )
    _sentry_initialised = True
    logger.info("Sentry initialised for environment '%s'", environment)
    return True


def record_ingestion_metrics(
    status: str,
    *,
    inserted: int,
    updated: int,
    skipped: int,
    failed: int,
    duration_seconds: float,
    release_total: Optional[int] = None,
) -> None:
    """Update Prometheus counters based on the latest ingestion run."""

    INGESTION_RUNS.labels(status=status).inc()
    INGESTION_ITEMS.labels(result="inserted").inc(inserted)
    INGESTION_ITEMS.labels(result="updated").inc(updated)
    INGESTION_ITEMS.labels(result="skipped").inc(skipped)
    INGESTION_ITEMS.labels(result="failed").inc(failed)
    INGESTION_DURATION.observe(max(duration_seconds, 0.0))

    if release_total is not None:
        RELEASE_GAUGE.set(release_total)

    if status == "completed":
        LAST_SUCCESS_GAUGE.set(time.time())


def record_scheduler_job_start(job: str, next_run_epoch: Optional[float] = None) -> None:
    """Mark a scheduler job as running and optionally set the next scheduled time."""

    SCHEDULER_JOB_ACTIVE.labels(job=job).set(1)
    if next_run_epoch is not None:
        SCHEDULER_NEXT_RUN.labels(job=job).set(next_run_epoch)


def record_scheduler_job_completion(job: str, status: str, *, duration_seconds: float) -> None:
    """Record completion of a scheduler-triggered job."""

    SCHEDULER_JOB_ACTIVE.labels(job=job).set(0)
    SCHEDULER_JOB_RUNS.labels(job=job, status=status).inc()
    SCHEDULER_JOB_DURATION.labels(job=job).observe(max(duration_seconds, 0.0))


def record_scheduler_job_skip(job: str, reason: str, next_run_epoch: Optional[float] = None) -> None:
    """Track when a scheduler job fire is skipped."""

    SCHEDULER_JOB_SKIPS.labels(job=job, reason=reason).inc()
    if next_run_epoch is not None:
        SCHEDULER_NEXT_RUN.labels(job=job).set(next_run_epoch)


def record_rss_fetch_metrics(feed_url: str, status: str, *, duration_seconds: float) -> None:
    """Record Prometheus metrics for RSS HTTP requests."""

    RSS_REQUESTS.labels(feed=feed_url, status=status).inc()
    RSS_REQUEST_DURATION.labels(feed=feed_url).observe(max(duration_seconds, 0.0))


def record_summary_metrics(status: str, *, duration_seconds: float) -> None:
    """Record metrics for summary generation attempts."""

    SUMMARY_GENERATIONS.labels(status=status).inc()
    SUMMARY_LATENCY.observe(max(duration_seconds, 0.0))


def record_http_request_metrics(method: str, endpoint: str, status_code: int, *, duration_seconds: float) -> None:
    """Track HTTP request volume and latency for the API."""

    status_label = str(status_code)
    HTTP_REQUESTS.labels(method=method, endpoint=endpoint, status=status_label).inc()
    HTTP_LATENCY.labels(method=method, endpoint=endpoint).observe(max(duration_seconds, 0.0))


def record_claim_verification_metrics(verdict: str, *, duration_seconds: float) -> None:
    """Capture claim verification outcomes and latency."""

    CLAIM_VERIFICATIONS.labels(verdict=verdict).inc()
    CLAIM_VERIFICATION_LATENCY.observe(max(duration_seconds, 0.0))


def render_metrics() -> tuple[bytes, str]:
    """Return serialized metrics along with content type."""

    payload = generate_latest(REGISTRY)
    return payload, CONTENT_TYPE_LATEST


def emit_synthetic_sentry_event(message: str = "Monitoring smoke test") -> None:
    """Send a small marker event to validate Sentry plumbing."""

    if not _sentry_initialised:
        logger.warning("Sentry is not initialised; synthetic event was skipped")
        return
    capture_message(message)
