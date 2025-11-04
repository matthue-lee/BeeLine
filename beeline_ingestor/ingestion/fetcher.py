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


class ArticleFetcher:
    """Fetch HTML content for a release link."""

    def __init__(self, config: FeedConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.config.user_agent})

    def fetch(self, url: str) -> FetchResult:
        """Fetch the given URL and return relevant metadata."""

        logger.debug("Fetching article %s", url)
        try:
            response = self.session.get(url, timeout=self.config.request_timeout.total_seconds())
            response.raise_for_status()
            content = response.text
        except requests.RequestException as exc:
            logger.warning("Article fetch failed for %s: %s", url, exc)
            response = getattr(exc, "response", None)
            status_code = response.status_code if response is not None else 0
            return FetchResult(url=url, final_url=url, status_code=status_code, fetched_at=datetime.now(timezone.utc), content=None)

        return FetchResult(
            url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            fetched_at=datetime.now(timezone.utc),
            content=response.text,
        )
