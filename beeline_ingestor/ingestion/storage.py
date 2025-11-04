"""Persistence helpers for ingestion outputs."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from ..config import AppConfig
from ..db import Database
from ..models import DocumentStatus, ReleaseDocument
from .cleaner import CleanResult
from .fetcher import FetchResult
from .rss import FeedEntry

logger = logging.getLogger(__name__)


class ReleaseRepository:
    """Repository abstraction for release documents."""

    def __init__(self, db: Database, config: AppConfig):
        self.db = db
        self.config = config

    def upsert(
        self,
        entry: FeedEntry,
        fetch: FetchResult | None,
        cleaned: CleanResult,
    ) -> tuple[ReleaseDocument, bool]:
        """Insert or update a release record, returning the ORM object and whether it was newly inserted."""

        with self.db.session() as session:
            existing = session.execute(select(ReleaseDocument).where(ReleaseDocument.id == entry.id)).scalar_one_or_none()
            if existing:
                was_inserted = False
                self._update_release(existing, entry, fetch, cleaned)
                session.add(existing)
                return existing, was_inserted

            document = ReleaseDocument(
                id=entry.id,
                title=entry.title,
                url=entry.url,
                published_at=entry.published_at,
                minister=None,
                portfolio=None,
                categories=entry.categories,
                text_raw=fetch.content if fetch else entry.summary,
                text_clean=cleaned.text,
                status=self._derive_status(fetch, cleaned),
                word_count=cleaned.word_count,
                fetched_at=fetch.fetched_at if fetch else datetime.now(timezone.utc),
                provenance=self._build_provenance(entry, fetch),
            )
            session.add(document)
            return document, True

    def _update_release(self, document: ReleaseDocument, entry: FeedEntry, fetch: FetchResult | None, cleaned: CleanResult) -> None:
        """Update an existing release while preserving better content."""

        document.title = entry.title
        document.url = entry.url
        document.published_at = entry.published_at or document.published_at
        document.categories = entry.categories or document.categories
        document.provenance.update({"last_feed": entry.feed_url})

        if fetch:
            document.fetched_at = fetch.fetched_at
            document.provenance.update({"final_url": fetch.final_url, "status_code": fetch.status_code})
            if fetch.content and (not document.text_raw or len(fetch.content) > len(document.text_raw)):
                document.text_raw = fetch.content

        # Only upgrade cleaned text when it is better than the existing version.
        if cleaned.text and (not document.text_clean or len(cleaned.text) > len(document.text_clean)):
            document.text_clean = cleaned.text
            document.word_count = cleaned.word_count

        document.status = self._derive_status(fetch, cleaned)

    def _derive_status(self, fetch: FetchResult | None, cleaned: CleanResult) -> DocumentStatus:
        """Determine document status based on fetch and cleaning results."""

        if fetch and fetch.content:
            if cleaned.text and cleaned.word_count >= self.config.min_content_length:
                return DocumentStatus.OK
            if cleaned.text:
                return DocumentStatus.PARTIAL
            return DocumentStatus.EMPTY_PARSE
        if cleaned.text:
            return DocumentStatus.PARTIAL
        return DocumentStatus.FAILED_FETCH

    def _build_provenance(self, entry: FeedEntry, fetch: FetchResult | None) -> dict:
        """Assemble provenance metadata for downstream auditing."""

        provenance = {
            "feed_url": entry.feed_url,
            "fetched_from_feed": datetime.now(timezone.utc).isoformat(),
        }
        if fetch:
            provenance.update(
                {
                    "article_status": fetch.status_code,
                    "final_url": fetch.final_url,
                    "article_fetched_at": fetch.fetched_at.isoformat(),
                }
            )
        return provenance
