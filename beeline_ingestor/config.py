"""Configuration helpers for the BeeLine ingestion service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Iterable, List


DEFAULT_FEED = "https://www.beehive.govt.nz/releases/feed"


@dataclass(slots=True)
class FeedConfig:
    """Configuration for RSS feed polling."""

    urls: List[str] = field(default_factory=lambda: [DEFAULT_FEED])
    user_agent: str = "BeeLineIngestor/0.1 (+https://example.com/contact)"
    request_timeout: timedelta = timedelta(seconds=20)
    max_retries: int = 2
    backoff_factor: float = 0.5


@dataclass(slots=True)
class DatabaseConfig:
    """Database connection settings."""

    uri: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///beeline.db"))
    echo: bool = field(default_factory=lambda: bool(int(os.getenv("SQLALCHEMY_ECHO", "0"))))


@dataclass(slots=True)
class AppConfig:
    """Top-level configuration aggregation."""

    feeds: FeedConfig = field(default_factory=FeedConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    min_content_length: int = int(os.getenv("MIN_CONTENT_LENGTH", "200"))
    enable_article_fetch: bool = bool(int(os.getenv("ENABLE_ARTICLE_FETCH", "1")))

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

        retries = os.getenv("HTTP_MAX_RETRIES")
        if retries:
            feeds.max_retries = int(retries)

        backoff = os.getenv("HTTP_BACKOFF_FACTOR")
        if backoff:
            feeds.backoff_factor = float(backoff)

        return cls(
            feeds=feeds,
            database=DatabaseConfig(),
            min_content_length=int(os.getenv("MIN_CONTENT_LENGTH", "200")),
            enable_article_fetch=bool(int(os.getenv("ENABLE_ARTICLE_FETCH", "1"))),
        )


def ensure_iterable(value: Iterable[str] | str) -> Iterable[str]:
    """Ensure a string or iterable of strings is returned as an iterable of strings."""

    if isinstance(value, str):
        return (value,)
    return value
