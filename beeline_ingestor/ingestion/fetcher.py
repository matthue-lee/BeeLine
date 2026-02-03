"""HTTP fetching utilities for release articles."""
from __future__ import annotations

import logging
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
        """Fetch the given URL and return relevant metadata."""

        try:
            response = self.session.get(
                url,
                timeout=self.config.request_timeout.total_seconds(),
                allow_redirects=True,
            )
            response.raise_for_status()
            return FetchResult(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                fetched_at=datetime.now(timezone.utc),
                content=response.text,
            )
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", 0)
            final_url = getattr(getattr(exc, "response", None), "url", url)
            logger.warning("Article fetch failed for %s: %s", url, exc)
            return FetchResult(
                url=url,
                final_url=str(final_url),
                status_code=status_code,
                fetched_at=datetime.now(timezone.utc),
                content=None,
                error=str(exc),
            )
