"""Thin client to enqueue downstream jobs via the Node queue service.

This uses a lightweight HTTP API exposed by the workers process. It is
internal-only (docker network) and intended for the ingestion pipeline.
"""
from __future__ import annotations

import json
import os
import time
import logging
import hashlib
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)


def make_idempotency_token(stage: str, **kwargs: Any) -> str:
    payload = json.dumps({"stage": stage, **kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class QueueDispatcher:
    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        self.base_url = base_url or os.getenv("QUEUE_SERVICE_URL", "http://localhost:9100")
        self.timeout = timeout

    def enqueue(self, stage: str, payload: Dict[str, Any]) -> str:
        url = f"{self.base_url}/internal/enqueue/{stage}"
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            job_id = data.get("job_id")
            if not job_id:
                raise RuntimeError(f"Enqueue response missing job_id: {data}")
            return str(job_id)
        except Exception as exc:  # network or JSON errors
            logger.warning("Queue enqueue failed for stage %s: %s", stage, exc)
            raise

