"""Utility helpers for ingestion pipeline."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


def compute_canonical_id(title: str, url: str) -> str:
    """Compute a stable ID using sha256 over normalized title and URL."""

    normalized = f"{title.strip().lower()}::{url.strip().lower()}".encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse RSS datetime strings into timezone-aware UTC timestamps."""

    if not value:
        return None
    try:
        dt = date_parser.parse(value)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError) as exc:
        logger.warning("Unable to parse datetime '%s': %s", value, exc)
        return None


def strip_empty(values: Iterable[str]) -> list[str]:
    """Return a list with blank strings removed and whitespace trimmed."""

    return [item.strip() for item in values if item and item.strip()]
