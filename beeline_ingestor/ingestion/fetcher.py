"""HTTP fetching utilities for release articles."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Callable, Optional

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
    content_length: Optional[int] = None
    attempts: int = 1
    incapsula_detected: bool = False
    headers: Optional[dict[str, str]] = None


class ArticleFetcher:
    """Fetch HTML content for a release link."""

    def __init__(
        self,
        config: FeedConfig,
        *,
        session: requests.Session | None = None,
        sleep_func: Callable[[float], None] | None = None,
        max_attempts: int = 3,
        backoff_initial: float = 2.0,
        backoff_max: float = 30.0,
    ):
        self.config = config
        self.session = session or requests.Session()
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
        self.max_attempts = max_attempts
        self.backoff_initial = max(0.5, backoff_initial)
        self.backoff_max = max(self.backoff_initial, backoff_max)
        self._sleep = sleep_func or time.sleep

    def fetch(self, url: str) -> FetchResult:
        """Fetch the given URL and return relevant metadata."""

        last_exc: Exception | None = None
        attempts = 0
        while attempts < self.max_attempts:
            attempts += 1
            start = perf_counter()
            try:
                response = self.session.get(
                    url,
                    timeout=self.config.request_timeout.total_seconds(),
                    allow_redirects=True,
                )
                incapsula = self._looks_like_incapsula(response)
                if incapsula:
                    return FetchResult(
                        url=url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        fetched_at=datetime.now(timezone.utc),
                        content=None,
                        error="Anti-bot challenge detected; skip this feed URL per policy",
                        content_length=len(response.content),
                        attempts=attempts,
                        incapsula_detected=True,
                        headers=dict(response.headers),
                    )
                response.raise_for_status()
                logger.debug("Fetched article %s in %.2fs", url, perf_counter() - start)
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    fetched_at=datetime.now(timezone.utc),
                    content=response.text,
                    content_length=len(response.content),
                    attempts=attempts,
                    incapsula_detected=incapsula,
                    headers=dict(response.headers),
                        error=(
                            "Anti-bot challenge detected; skip this feed URL per policy"
                            if incapsula
                            else None
                        ),
                )
            except requests.RequestException as exc:
                last_exc = exc
                wait_time = self._compute_backoff(attempts)
                logger.warning(
                    "Article fetch failed for %s (attempt %s/%s): %s",
                    url,
                    attempts,
                    self.max_attempts,
                    exc,
                )
                if attempts >= self.max_attempts:
                    break
                self._sleep(wait_time)

        status_code = getattr(getattr(last_exc, "response", None), "status_code", 0)
        final_url = getattr(getattr(last_exc, "response", None), "url", url)
        return FetchResult(
            url=url,
            final_url=str(final_url),
            status_code=status_code,
            fetched_at=datetime.now(timezone.utc),
            content=None,
            error=str(last_exc) if last_exc else "exhausted attempts",
            attempts=attempts,
        )

    def _compute_backoff(self, attempts: int) -> float:
        """Return exponential backoff seconds for a failed request."""

        backoff = self.backoff_initial * (2 ** (attempts - 1))
        return min(backoff, self.backoff_max)

    @staticmethod
    def _looks_like_incapsula(response: requests.Response) -> bool:
        """Return True if the payload resembles an Incapsula challenge page."""

        if response.status_code in {403, 503}:
            text = response.text[:2048]
            return "Incapsula" in text or "Request unsuccessful" in text
        return False
