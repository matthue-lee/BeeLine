"""News-ingestion specific metrics isolated from the main registry consumers."""
from __future__ import annotations

import time
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram

from .observability import REGISTRY

NEWS_INGESTION_RUNS = Counter(
    "beeline_news_ingestion_runs_total",
    "News article ingestion runs grouped by status.",
    ("status",),
    registry=REGISTRY,
)

NEWS_INGESTION_DURATION = Histogram(
    "beeline_news_ingestion_run_seconds",
    "Wall-clock duration of news article ingestion runs.",
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
    registry=REGISTRY,
)

NEWS_ARTICLE_EVENTS = Counter(
    "beeline_news_articles_processed_total",
    "News articles processed grouped by outcome.",
    ("result",),
    registry=REGISTRY,
)

NEWS_ARTICLE_GAUGE = Gauge(
    "beeline_news_articles_total",
    "Current number of stored news articles available for cross-linking.",
    registry=REGISTRY,
)

NEWS_LAST_SUCCESS_GAUGE = Gauge(
    "beeline_news_ingestion_last_success_unixtime",
    "Unix timestamp for the most recent successful news ingestion run.",
    registry=REGISTRY,
)

NEWS_ARTICLES_PRUNED = Counter(
    "beeline_news_articles_pruned_total",
    "News articles removed via retention policies.",
    registry=REGISTRY,
)


def record_news_ingestion_metrics(
    status: str,
    *,
    seen: int,
    inserted: int,
    updated: int,
    pruned: int,
    duration_seconds: float,
    article_total: Optional[int] = None,
) -> None:
    """Track metrics for the external news ingestion pipeline."""

    NEWS_INGESTION_RUNS.labels(status=status).inc()
    NEWS_ARTICLE_EVENTS.labels(result="seen").inc(seen)
    NEWS_ARTICLE_EVENTS.labels(result="inserted").inc(inserted)
    NEWS_ARTICLE_EVENTS.labels(result="updated").inc(updated)
    if pruned:
        NEWS_ARTICLES_PRUNED.inc(pruned)
    NEWS_INGESTION_DURATION.observe(max(duration_seconds, 0.0))

    if article_total is not None:
        NEWS_ARTICLE_GAUGE.set(article_total)

    if status == "completed":
        NEWS_LAST_SUCCESS_GAUGE.set(time.time())
