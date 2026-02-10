import datetime as dt
import pathlib
import sys
from typing import List

import pytest
import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor.config import FeedConfig
from beeline_ingestor.ingestion.rss import FeedClient


class FakeResponse:
    def __init__(self, content: bytes, status: int = 200, headers: dict | None = None) -> None:
        self.content = content
        self.status_code = status
        self.headers = headers or {}
        self.text = content.decode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"Status {self.status_code}")


class FakeSession:
    def __init__(self, responses: List[object]):
        self._responses = responses
        self.headers: dict[str, str] = {}
        self.calls: list[str] = []

    def get(self, url: str, timeout: float) -> FakeResponse:
        self.calls.append(url)
        if not self._responses:
            raise RuntimeError("No responses left")
        payload = self._responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return payload


FEED_CONTENT = b"""
<rss><channel>
  <item>
    <title>Test Release</title>
    <link>https://example.com/r1</link>
    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""


def make_config(**overrides):
    base = FeedConfig(urls=["https://example.com/feed"], respect_robots=False)
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_feed_client_sets_user_agent_header():
    config = make_config(user_agent="CustomAgent/1.0")
    session = requests.Session()
    FeedClient(config, session=session)
    assert session.headers["User-Agent"] == "CustomAgent/1.0"


def test_feed_client_waits_when_rate_limited():
    config = make_config()
    session = FakeSession([FakeResponse(FEED_CONTENT)])
    sleep_calls: list[float] = []

    client = FeedClient(config, session=session, sleep_func=sleep_calls.append)
    client._next_allowed[config.urls[0]] = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1)

    entries = client.fetch()
    assert entries, "expected entries to be parsed"
    assert sleep_calls[0] == pytest.approx(1.0, rel=0.1)


def test_feed_client_retries_on_request_error():
    config = make_config(max_attempts=2)
    session = FakeSession([
        requests.ConnectionError("boom"),
        FakeResponse(FEED_CONTENT),
    ])
    client = FeedClient(config, session=session, sleep_func=lambda _: None)

    entries = client.fetch()
    assert len(entries) == 1
    assert session.calls.count(config.urls[0]) == 2


def test_feed_client_skips_when_robots_disallows(monkeypatch):
    config = make_config(respect_robots=True)
    session = FakeSession([FakeResponse(FEED_CONTENT)])
    client = FeedClient(config, session=session)
    monkeypatch.setattr(client, "_is_allowed_by_robots", lambda url: False)

    entries = client.fetch()
    assert entries == []
    assert session.calls == []
