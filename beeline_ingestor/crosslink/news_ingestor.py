"""Fetch and store external news articles from configured RSS feeds."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import requests

from ..config import AppConfig
from ..db import Database
from ..utils import parse_datetime
from .articles import ArticleInput, NewsArticleRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NewsIngestResult:
    """Simple stats for news article sync runs."""

    total_feeds: int
    articles_seen: int
    inserted: int
    updated: int


class NewsIngestor:
    """Fetch RSS feeds and persist article metadata for cross linking."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.database = Database(config)
        self.database.create_all()
        self.repository = NewsArticleRepository(self.database)
        self.session = requests.Session()
        self.retention_days = config.crosslink.retention_days

    def run(self) -> NewsIngestResult:
        feeds = self.config.crosslink.feeds
        inserted = updated = 0
        seen = 0

        for feed_url in feeds:
            logger.info("Fetching external feed %s", feed_url)
            try:
                response = self.session.get(feed_url, timeout=30)
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("Failed to fetch %s: %s", feed_url, exc)
                continue

            parsed = feedparser.parse(response.content)
            source_name = parsed.feed.get("title") or urlparse(feed_url).netloc
            for entry in parsed.entries:
                seen += 1
                article = self._build_article(entry, source_name)
                if not article:
                    continue
                _, was_inserted = self.repository.upsert(article)
                if was_inserted:
                    inserted += 1
                else:
                    updated += 1

        logger.info(
            "News ingest complete feeds=%s seen=%s inserted=%s updated=%s",
            len(feeds),
            seen,
            inserted,
            updated,
        )
        pruned = self.repository.prune(self.retention_days)
        if pruned:
            logger.info("Pruned %s stale news articles older than %s days", pruned, self.retention_days)
        return NewsIngestResult(total_feeds=len(feeds), articles_seen=seen, inserted=inserted, updated=updated)

    def _build_article(self, entry: dict, source_name: str) -> ArticleInput | None:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            return None

        published = parse_datetime(entry.get("published") or entry.get("updated"))
        summary = entry.get("summary") or entry.get("description")
        text_clean = summary

        return ArticleInput(
            title=title,
            url=link,
            source=source_name,
            summary=summary.strip() if summary else None,
            text_clean=text_clean.strip() if text_clean else None,
            published_at=published,
        )


def main() -> None:
    config = AppConfig.from_env()
    ingestor = NewsIngestor(config)
    ingestor.run()


if __name__ == "__main__":
    main()
