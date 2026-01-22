"""HTTP fetching utilities for release articles."""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

from ..config import FeedConfig

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FetchResult:
    """Result payload for article fetch attempts."""

    url: str
    final_url: str
    status_code: int
    fetched_at: datetime
    content: Optional[str]
    error: Optional[str] = None


class ArticleFetcher:
    """Fetch HTML content for a release link."""

    def __init__(self, config: FeedConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-NZ,en;q=0.9",
                "Connection": "keep-alive",
                "Referer": "https://www.beehive.govt.nz/",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document",
            }
        )

    def fetch(self, url: str) -> FetchResult:
        """Fetch the given URL and return relevant metadata with retry/backoff."""

        last_error: Optional[str] = None
        for candidate in self._candidate_urls(url):
            for attempt in range(self.config.max_retries + 1):
                if attempt:
                    sleep_seconds = self._backoff_delay(attempt)
                    logger.debug("Retrying %s in %.2fs", candidate, sleep_seconds)
                    time.sleep(sleep_seconds)

                try:
                    response = self.session.get(
                        candidate,
                        timeout=self.config.request_timeout.total_seconds(),
                        allow_redirects=True,
                        headers={"User-Agent": self.config.user_agent},
                    )
                    response.raise_for_status()
                    if self._looks_blocked(response.text):
                        last_error = "blocked"
                        logger.warning(
                            "Article fetch blocked for %s (attempt %s/%s)",
                            candidate,
                            attempt + 1,
                            self.config.max_retries + 1,
                        )
                        break  # try alternative URL variant
                    return FetchResult(
                        url=url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        fetched_at=datetime.now(timezone.utc),
                        content=response.text,
                    )
                except requests.RequestException as exc:
                    last_error = str(exc)
                    logger.warning(
                        "Article fetch failed for %s (attempt %s/%s): %s",
                        candidate,
                        attempt + 1,
                        self.config.max_retries + 1,
                        exc,
                    )
            if last_error == "blocked":
                continue

        return FetchResult(
            url=url,
            final_url=url,
            status_code=0,
            fetched_at=datetime.now(timezone.utc),
            content=None,
            error=last_error,
        )

    def _backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff with jitter for retries."""

        base = self.config.backoff_factor * (2 ** (attempt - 1))
        jitter = random.uniform(0, 0.5)
        return min(self.config.request_timeout.total_seconds(), base + jitter)

    @staticmethod
    def _candidate_urls(url: str) -> list[str]:
        """Return possible URL variants to bypass CDN blocking (e.g., AMP pages)."""

        candidates = [url]
        base, _, _ = url.partition("?")
        amp_query = f"{base}?amp"
        amp_path = base.rstrip("/") + "/amp"
        for candidate in (amp_query, amp_path):
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates

    @staticmethod
    def _looks_blocked(content: str) -> bool:
        """Detect common CDN block pages so they can be retried later."""

        markers = ["_Incapsula_Resource", "Request unsuccessful", "Incapsula"]
        return any(marker in content for marker in markers)
