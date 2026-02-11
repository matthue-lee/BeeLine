"""Redis-backed cache for storing summary payloads."""
from __future__ import annotations

import json
import os
from typing import Optional

import redis

from ..schemas.summary import SummaryPayload


class SummaryCache:
    """Simple TTL cache used to avoid re-fetching summaries from the DB/API."""

    def __init__(self, *, redis_url: Optional[str] = None, ttl_seconds: int = 86400):
        self.redis_url = redis_url or os.getenv("SUMMARY_CACHE_REDIS_URL") or os.getenv("REDIS_URL")
        self.ttl_seconds = ttl_seconds
        self.client: redis.Redis | None = None
        if self.redis_url:
            self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)

    def get(self, release_id: str) -> SummaryPayload | None:
        if not self.client:
            return None
        raw = self.client.get(self._key(release_id))
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self.client.delete(self._key(release_id))
            return None
        try:
            return SummaryPayload.from_dict(payload)
        except ValueError:
            self.client.delete(self._key(release_id))
            return None

    def set(self, release_id: str, payload: SummaryPayload) -> None:
        if not self.client:
            return
        data = json.dumps(payload.to_dict())
        self.client.setex(self._key(release_id), self.ttl_seconds, data)

    def invalidate(self, release_id: str) -> None:
        if not self.client:
            return
        self.client.delete(self._key(release_id))

    def _key(self, release_id: str) -> str:
        return f"summary:{release_id}"
