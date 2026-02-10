"""RSS feed fetching and parsing helpers."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Callable, Iterable, List, Sequence
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import requests

from ..config import FeedConfig
from ..observability import record_rss_fetch_metrics
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

    def __init__(
        self,
        config: FeedConfig,
        *,
        session: requests.Session | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.config.user_agent})
        self._sleep = sleep_func or time.sleep
        self._next_allowed: dict[str, datetime] = {}
        self._current_backoff: dict[str, timedelta] = {}
        self._robots_cache: dict[str, tuple[RobotFileParser | None, float]] = {}

    def fetch(self, since: datetime | None = None, until: datetime | None = None) -> List[FeedEntry]:
        """Fetch entries from all configured feeds, optionally filtering by date range."""

        entries: list[FeedEntry] = []
        for url in self.config.urls:
            if self.config.respect_robots and not self._is_allowed_by_robots(url):
                logger.warning("robots.txt disallows fetching feed %s; skipping", url)
                record_rss_fetch_metrics(url, "robots", duration_seconds=0.0)
                continue

            logger.info("Fetching RSS feed %s", url)
            entries.extend(self._fetch_with_retries(url, since, until))
        return entries

    def _fetch_with_retries(self, url: str, since: datetime | None, until: datetime | None) -> List[FeedEntry]:
        attempts = 0
        max_attempts = max(1, self.config.max_attempts)
        while attempts < max_attempts:
            attempts += 1
            self._wait_for_slot(url)
            start = perf_counter()
            status_label = "error"
            try:
                response = self.session.get(url, timeout=self.config.request_timeout.total_seconds())
                status_label = str(response.status_code)
                if response.status_code == 429:
                    retry_delay = self._retry_after_delay(response)
                    self._apply_backoff(url, minimum_delay=retry_delay)
                response.raise_for_status()
            except requests.HTTPError as exc:
                duration = perf_counter() - start
                record_rss_fetch_metrics(url, status_label, duration_seconds=duration)
                logger.warning("HTTP error when fetching %s (attempt %s/%s): %s", url, attempts, max_attempts, exc)
                self._apply_backoff(url)
                if attempts >= max_attempts:
                    return []
            except requests.RequestException as exc:
                duration = perf_counter() - start
                record_rss_fetch_metrics(url, "error", duration_seconds=duration)
                logger.warning(
                    "Request error when fetching %s (attempt %s/%s): %s", url, attempts, max_attempts, exc
                )
                self._apply_backoff(url)
                if attempts >= max_attempts:
                    return []
            else:
                duration = perf_counter() - start
                record_rss_fetch_metrics(url, status_label, duration_seconds=duration)
                self._schedule_cooldown(url)
                parsed = feedparser.parse(response.content)
                return self._parse_feed(parsed, url, since, until)
        return []

    def _wait_for_slot(self, url: str) -> None:
        allowed_at = self._next_allowed.get(url)
        if not allowed_at:
            return
        now = datetime.now(timezone.utc)
        if allowed_at <= now:
            return
        delay = (allowed_at - now).total_seconds()
        if delay > 0:
            logger.debug("Rate limiting %s for %.2fs", url, delay)
            self._sleep(delay)

    def _schedule_cooldown(self, url: str) -> None:
        cooldown = self.config.per_feed_cooldown
        if cooldown.total_seconds() <= 0:
            self._next_allowed.pop(url, None)
        else:
            self._next_allowed[url] = datetime.now(timezone.utc) + cooldown
        self._current_backoff.pop(url, None)

    def _apply_backoff(self, url: str, *, minimum_delay: timedelta | None = None) -> None:
        previous = self._current_backoff.get(url)
        if previous is None:
            delay = self.config.retry_backoff_initial
        else:
            delay = min(previous * 2, self.config.retry_backoff_max)
        if minimum_delay and minimum_delay > delay:
            delay = minimum_delay
        self._current_backoff[url] = delay
        self._next_allowed[url] = datetime.now(timezone.utc) + delay

    def _retry_after_delay(self, response: requests.Response) -> timedelta | None:
        retry_after = response.headers.get("Retry-After")
        if not retry_after:
            return None
        try:
            seconds = int(retry_after.strip())
        except ValueError:
            return None
        return timedelta(seconds=max(1, seconds))

    def _is_allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return True
        base = f"{parsed.scheme}://{parsed.netloc}"
        ttl_seconds = max(1, int(self.config.robots_cache_ttl.total_seconds()))
        cache_entry = self._robots_cache.get(base)
        now = time.monotonic()
        parser: RobotFileParser | None
        if cache_entry and cache_entry[1] > now:
            parser = cache_entry[0]
        else:
            parser = self._load_robots(base)
            self._robots_cache[base] = (parser, now + ttl_seconds)
        if not parser:
            return True
        return parser.can_fetch(self.config.user_agent, url)

    def _load_robots(self, base: str) -> RobotFileParser | None:
        robots_url = urljoin(base, "/robots.txt")
        try:
            response = self.session.get(robots_url, timeout=self.config.request_timeout.total_seconds())
            if response.status_code >= 400:
                logger.debug("robots.txt %s returned %s", robots_url, response.status_code)
                return None
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            return parser
        except requests.RequestException as exc:
            logger.debug("Unable to fetch robots.txt %s: %s", robots_url, exc)
            return None

    def _parse_feed(
        self,
        parsed_feed: feedparser.FeedParserDict,
        url: str,
        since: datetime | None,
        until: datetime | None,
    ) -> List[FeedEntry]:
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
            if until and published and published > until:
                logger.debug("Skipping %s; newer than %s", link, until)
                continue

            categories = strip_empty(self._extract_categories(entry))
            summary = entry.get("summary") or entry.get("description")
            canonical_id = compute_canonical_id(title, link, published)

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
