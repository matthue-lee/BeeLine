from typing import List
import pathlib
import sys

import pytest
import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor.config import FeedConfig
from beeline_ingestor.ingestion.fetcher import ArticleFetcher


class FakeResponse:
    def __init__(
        self,
        text: str,
        *,
        status: int = 200,
        url: str = "https://example.com/release",
        headers: dict | None = None,
    ) -> None:
        self.text = text
        self.status_code = status
        self.url = url
        self.headers = headers or {"Content-Type": "text/html"}
        self.content = text.encode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"Status {self.status_code}")


class FakeSession:
    def __init__(self, responses: List[object]):
        self._responses = responses
        self.headers: dict[str, str] = {}

    def get(self, url: str, timeout: float, allow_redirects: bool) -> FakeResponse:
        if not self._responses:
            raise RuntimeError("No responses queued")
        payload = self._responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return payload


def make_fetcher(responses: List[object], **kwargs) -> ArticleFetcher:
    config = FeedConfig()
    return ArticleFetcher(config, session=FakeSession(responses), sleep_func=lambda _: None, **kwargs)


def test_fetcher_returns_metadata():
    html = "<html><body><p>Hello</p></body></html>"
    fetcher = make_fetcher([FakeResponse(html)])

    result = fetcher.fetch("https://example.com/release")

    assert result.content_length == len(html.encode("utf-8"))
    assert result.attempts == 1
    assert result.error is None


def test_fetcher_retries_on_failure():
    html = "<html>ok</html>"
    fetcher = make_fetcher([
        requests.ConnectionError("boom"),
        FakeResponse(html),
    ], max_attempts=2)

    result = fetcher.fetch("https://example.com/retry")

    assert result.attempts == 2
    assert result.content == html


def test_fetcher_marks_incapsula_challenge():
    html = "<html><body>Request unsuccessful. Incapsula</body></html>"
    fetcher = make_fetcher([FakeResponse(html, status=403)])

    result = fetcher.fetch("https://example.com/incapsula")

    assert result.incapsula_detected is True
    assert result.error and "Anti-bot" in result.error


def test_fetcher_returns_error_after_exhausting_attempts():
    fetcher = make_fetcher([requests.Timeout("boom"), requests.Timeout("boom")], max_attempts=2)

    result = fetcher.fetch("https://example.com/timeout")

    assert result.content is None
    assert "boom" in result.error
    assert result.attempts == 2
