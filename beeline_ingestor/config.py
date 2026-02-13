"""Configuration helpers for the BeeLine ingestion service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from sqlalchemy.engine import make_url

from .entity_extraction.config import EntityExtractionConfig
from .circuit_breaker import BudgetLimits


DEFAULT_FEED = "https://www.beehive.govt.nz/releases/feed"
DEFAULT_NEWS_FEEDS = [
    "https://www.stuff.co.nz/rss",
    "https://thespinoff.co.nz/feed",
    "https://www.rnz.co.nz/rss/national.xml",
    "https://nzmanufacturer.co.nz/feed/"
]


@dataclass(slots=True)
class FeedConfig:
    """Configuration for RSS feed polling."""

    urls: List[str] = field(default_factory=lambda: [DEFAULT_FEED])
    user_agent: str = "BeeLineReleaseMonitor/1.0 (+mailto:matthew.r.c.lee@outlook.com)"
    request_timeout: timedelta = timedelta(seconds=30)
    max_attempts: int = 3
    per_feed_cooldown: timedelta = timedelta(seconds=5)
    retry_backoff_initial: timedelta = timedelta(seconds=10)
    retry_backoff_max: timedelta = timedelta(minutes=5)
    respect_robots: bool = True
    robots_cache_ttl: timedelta = timedelta(hours=6)


@dataclass(slots=True)
class DatabaseConfig:
    """Database connection settings."""

    uri: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///db/beeline.db"))
    echo: bool = field(default_factory=lambda: bool(int(os.getenv("SQLALCHEMY_ECHO", "0"))))

    def ensure_path(self) -> None:
        url = make_url(self.uri)
        if url.get_backend_name() != "sqlite":
            return
        db_path = url.database or ""
        if not db_path or db_path == ":memory:":
            return
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class CrossLinkConfig:
    """Configuration for cross-source article fetching and linking."""

    feeds: List[str] = field(default_factory=lambda: DEFAULT_NEWS_FEEDS.copy())
    max_articles: int = 200
    link_limit: int = 3
    retention_days: int = 60


@dataclass(slots=True)
class SchedulerJobConfig:
    """Base configuration shared by scheduled jobs."""

    enabled: bool = True
    interval: timedelta = timedelta(minutes=15)
    initial_delay: timedelta = timedelta(seconds=30)


@dataclass(slots=True)
class ReleaseSchedulerConfig(SchedulerJobConfig):
    """Release ingestion specific scheduler settings."""

    interval: timedelta = timedelta(minutes=15)
    lookback: timedelta = timedelta(hours=6)
    source_label: str = "rss"


@dataclass(slots=True)
class SchedulerConfig:
    """Top-level scheduler behaviour toggles and job configs."""

    enabled: bool = True
    metrics_port: int = 9101
    release_ingest: ReleaseSchedulerConfig = field(default_factory=ReleaseSchedulerConfig)
    news_ingest: SchedulerJobConfig = field(default_factory=lambda: SchedulerJobConfig(interval=timedelta(hours=1), initial_delay=timedelta(minutes=1)))


@dataclass(slots=True)
class AppConfig:
    """Top-level configuration aggregation."""

    feeds: FeedConfig = field(default_factory=FeedConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    min_content_length: int = int(os.getenv("MIN_CONTENT_LENGTH", "200"))
    enable_article_fetch: bool = bool(int(os.getenv("ENABLE_ARTICLE_FETCH", "1")))
    crosslink: CrossLinkConfig = field(default_factory=CrossLinkConfig)
    enable_entity_extraction: bool = bool(int(os.getenv("ENABLE_ENTITY_EXTRACTION", "1")))
    entity_extraction: EntityExtractionConfig = field(default_factory=EntityExtractionConfig)
    sentry_dsn: Optional[str] = None
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.0
    sentry_profiles_sample_rate: float = 0.0
    cost_limits: BudgetLimits = field(default_factory=lambda: BudgetLimits(50.0, 600.0, 12000.0))
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Construct configuration from process environment."""

        feed_urls = os.getenv("BEEHIVE_FEEDS")
        feeds = FeedConfig()
        if feed_urls:
            feeds.urls = [u.strip() for u in feed_urls.split(",") if u.strip()]

        ua = os.getenv("HTTP_USER_AGENT")
        if ua:
            feeds.user_agent = ua

        timeout = os.getenv("HTTP_TIMEOUT_SECONDS")
        if timeout:
            feeds.request_timeout = timedelta(seconds=int(timeout))

        max_attempts = os.getenv("RSS_MAX_ATTEMPTS")
        if max_attempts:
            feeds.max_attempts = max(1, int(max_attempts))

        cooldown = os.getenv("RSS_COOLDOWN_SECONDS")
        if cooldown:
            feeds.per_feed_cooldown = timedelta(seconds=max(0, int(cooldown)))

        backoff_initial = os.getenv("RSS_BACKOFF_INITIAL_SECONDS")
        if backoff_initial:
            feeds.retry_backoff_initial = timedelta(seconds=max(1, int(backoff_initial)))

        backoff_max = os.getenv("RSS_BACKOFF_MAX_SECONDS")
        if backoff_max:
            feeds.retry_backoff_max = timedelta(seconds=max(1, int(backoff_max)))

        respect_robots = os.getenv("RSS_RESPECT_ROBOTS")
        if respect_robots is not None:
            feeds.respect_robots = bool(int(respect_robots))

        robots_cache = os.getenv("RSS_ROBOTS_CACHE_SECONDS")
        if robots_cache:
            feeds.robots_cache_ttl = timedelta(seconds=max(60, int(robots_cache)))

        crosslink = CrossLinkConfig()
        news_feeds = os.getenv("CROSSLINK_FEEDS")
        if news_feeds:
            crosslink.feeds = [u.strip() for u in news_feeds.split(",") if u.strip()]

        link_limit = os.getenv("CROSSLINK_LINK_LIMIT")
        if link_limit:
            crosslink.link_limit = int(link_limit)

        max_articles = os.getenv("CROSSLINK_MAX_ARTICLES")
        if max_articles:
            crosslink.max_articles = int(max_articles)

        retention = os.getenv("CROSSLINK_RETENTION_DAYS")
        if retention:
            crosslink.retention_days = int(retention)

        database = DatabaseConfig()
        database.ensure_path()

        breaker_limits = BudgetLimits(
            hourly_usd=float(os.getenv("CIRCUIT_BREAKER_HOURLY_USD", "50")),
            daily_usd=float(os.getenv("CIRCUIT_BREAKER_DAILY_USD", "600")),
            monthly_usd=float(os.getenv("CIRCUIT_BREAKER_MONTHLY_USD", "12000")),
        )

        scheduler = SchedulerConfig(
            enabled=bool(int(os.getenv("SCHEDULER_ENABLED", "1"))),
            metrics_port=int(os.getenv("SCHEDULER_METRICS_PORT", "9101")),
        )
        release_enabled = os.getenv("SCHEDULER_RELEASE_ENABLED")
        if release_enabled is not None:
            scheduler.release_ingest.enabled = bool(int(release_enabled))
        release_interval = os.getenv("SCHEDULER_RELEASE_INTERVAL_MINUTES")
        if release_interval:
            scheduler.release_ingest.interval = timedelta(minutes=max(1, int(release_interval)))
        release_initial_delay = os.getenv("SCHEDULER_RELEASE_INITIAL_DELAY_SECONDS")
        if release_initial_delay:
            scheduler.release_ingest.initial_delay = timedelta(seconds=max(0, int(release_initial_delay)))
        release_lookback = os.getenv("SCHEDULER_RELEASE_LOOKBACK_HOURS")
        if release_lookback:
            scheduler.release_ingest.lookback = timedelta(hours=max(1, int(release_lookback)))
        release_source = os.getenv("SCHEDULER_RELEASE_SOURCE_LABEL")
        if release_source:
            scheduler.release_ingest.source_label = release_source

        news_enabled = os.getenv("SCHEDULER_NEWS_ENABLED")
        if news_enabled is not None:
            scheduler.news_ingest.enabled = bool(int(news_enabled))
        news_interval = os.getenv("SCHEDULER_NEWS_INTERVAL_MINUTES")
        if news_interval:
            scheduler.news_ingest.interval = timedelta(minutes=max(1, int(news_interval)))
        news_initial_delay = os.getenv("SCHEDULER_NEWS_INITIAL_DELAY_SECONDS")
        if news_initial_delay:
            scheduler.news_ingest.initial_delay = timedelta(seconds=max(0, int(news_initial_delay)))

        return cls(
            feeds=feeds,
            database=database,
            min_content_length=int(os.getenv("MIN_CONTENT_LENGTH", "200")),
            enable_article_fetch=bool(int(os.getenv("ENABLE_ARTICLE_FETCH", "1"))),
            crosslink=crosslink,
            enable_entity_extraction=bool(int(os.getenv("ENABLE_ENTITY_EXTRACTION", "1"))),
            entity_extraction=EntityExtractionConfig(),
            sentry_dsn=os.getenv("SENTRY_DSN"),
            sentry_environment=os.getenv("SENTRY_ENVIRONMENT", os.getenv("FLASK_ENV", "development")),
            sentry_traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
            sentry_profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0")),
            cost_limits=breaker_limits,
            scheduler=scheduler,
        )


def ensure_iterable(value: Iterable[str] | str) -> Iterable[str]:
    """Ensure a string or iterable of strings is returned as an iterable of strings."""

    if isinstance(value, str):
        return (value,)
    return value
