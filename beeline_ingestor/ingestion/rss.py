"""RSS feed fetching and parsing helpers."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Sequence

import feedparser
import requests

from ..config import FeedConfig
from ..utils import compute_canonical_id, parse_datetime, strip_empty

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FeedEntry:
    """Normalized RSS entry with essential metadata."""

    id: str
    title: str
    url: str
    published_at: datetime | None
    categories: list[str]
    summary: str | None
    feed_url: str


class FeedClient:
    """Client responsible for fetching and parsing Beehive RSS feeds."""

    def __init__(self, config: FeedConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.config.user_agent})

    def fetch(self, since: datetime | None = None) -> List[FeedEntry]:
        """Fetch entries from all configured feeds, optionally filtering by publish date."""

        entries: list[FeedEntry] = []
        for url in self.config.urls:
            logger.info("Fetching RSS feed %s", url)
            try:
                response = self.session.get(url, timeout=self.config.request_timeout.total_seconds())
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.error("Failed to fetch feed %s: %s", url, exc)
                continue

            parsed = feedparser.parse(response.content)
            entries.extend(self._parse_feed(parsed, url, since))
        return entries

    def _parse_feed(self, parsed_feed: feedparser.FeedParserDict, url: str, since: datetime | None) -> List[FeedEntry]:
        """Convert parsed feed entries into canonical `FeedEntry` objects."""

        parsed_entries: list[FeedEntry] = []
        for entry in parsed_feed.entries:
            title: str = entry.get("title", "").strip()
            link: str = entry.get("link", "").strip()
            if not title or not link:
                logger.debug("Skipping entry missing title or link")
                continue

            published = parse_datetime(entry.get("published") or entry.get("updated"))
            if since and published and published < since:
                logger.debug("Skipping %s; older than %s", link, since)
                continue

            categories = strip_empty(self._extract_categories(entry))
            summary = entry.get("summary") or entry.get("description")
            canonical_id = compute_canonical_id(title, link)

            parsed_entries.append(
                FeedEntry(
                    id=canonical_id,
                    title=title,
                    url=link,
                    published_at=published,
                    categories=categories,
                    summary=summary.strip() if summary else None,
                    feed_url=url,
                )
            )
        return parsed_entries

    @staticmethod
    def _extract_categories(entry: feedparser.FeedParserDict) -> Sequence[str]:
        """Extract category terms from RSS entry."""

        tags = entry.get("tags") or []
        terms: list[str] = []
        for tag in tags:
            term = tag.get("term") if isinstance(tag, dict) else None
            if term:
                terms.append(term)
        return terms
