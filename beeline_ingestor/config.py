"""Configuration helpers for the BeeLine ingestion service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from sqlalchemy.engine import make_url

from .entity_extraction.config import EntityExtractionConfig


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
        )


def ensure_iterable(value: Iterable[str] | str) -> Iterable[str]:
    """Ensure a string or iterable of strings is returned as an iterable of strings."""

    if isinstance(value, str):
        return (value,)
    return value
