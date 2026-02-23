"""Persistence helpers for ingestion outputs."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select

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
                provenance=self._build_provenance(entry, fetch, cleaned),
            )
            self._apply_clean_metadata(document, cleaned)
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
        if cleaned.text and (not document.text_clean or cleaned.word_count > (document.word_count or 0)):
            document.text_clean = cleaned.text
            document.word_count = cleaned.word_count
            if cleaned.excerpt:
                document.provenance["cleaner_excerpt"] = cleaned.excerpt
            if cleaned.removed_sections:
                document.provenance["cleaner_removed_sections"] = cleaned.removed_sections

        document.status = self._derive_status(fetch, cleaned)
        document.provenance = self._build_provenance(entry, fetch, cleaned, existing=document.provenance)
        self._apply_clean_metadata(document, cleaned)

    def _derive_status(self, fetch: FetchResult | None, cleaned: CleanResult) -> DocumentStatus:
        """Determine document status based on fetch and cleaning results."""

        if fetch and fetch.content:
            if cleaned.text and cleaned.word_count >= self.config.min_content_length:
                return DocumentStatus.OK
            if cleaned.text:
                return DocumentStatus.PARTIAL
            return DocumentStatus.EMPTY_PARSE
        if fetch and fetch.error:
            if cleaned.text:
                return DocumentStatus.PARTIAL
            return DocumentStatus.FAILED_FETCH
        if cleaned.text:
            return DocumentStatus.PARTIAL
        return DocumentStatus.FAILED_FETCH

    def _build_provenance(
        self,
        entry: FeedEntry,
        fetch: FetchResult | None,
        cleaned: CleanResult,
        *,
        existing: Optional[dict] = None,
    ) -> dict:
        """Assemble provenance metadata for downstream auditing."""

        provenance = existing.copy() if existing else {}
        provenance.update(
            {
                "feed_url": entry.feed_url,
                "fetched_from_feed": datetime.now(timezone.utc).isoformat(),
                "feed_categories": entry.categories,
                "clean_word_count": cleaned.word_count,
            }
        )
        if cleaned.excerpt:
            provenance["cleaner_excerpt"] = cleaned.excerpt
        if cleaned.removed_sections:
            provenance["cleaner_removed_sections"] = cleaned.removed_sections
        if fetch:
            provenance.update(
                {
                    "article_status": fetch.status_code,
                    "final_url": fetch.final_url,
                    "article_fetched_at": fetch.fetched_at.isoformat(),
                    "article_attempts": fetch.attempts,
                }
            )
            if fetch.error:
                provenance["article_error"] = fetch.error
            if fetch.content_length is not None:
                provenance["article_content_length"] = fetch.content_length
            if fetch.incapsula_detected:
                provenance["incapsula_detected"] = True
        return provenance

    def _apply_clean_metadata(self, document: ReleaseDocument, cleaned: CleanResult) -> None:
        if not cleaned.metadata:
            return
        if document.provenance is None:
            document.provenance = {}
        metadata = cleaned.metadata
        if metadata.get("ministers"):
            document.provenance["page_ministers"] = metadata["ministers"]
            document.ministers = metadata["ministers"]
            if metadata["ministers"]:
                document.minister = metadata["ministers"][0]
        if metadata.get("tags"):
            document.provenance["page_tags"] = metadata["tags"]

    def count_documents(self) -> int:
        """Return the total number of release documents currently stored."""

        with self.db.session() as session:
            return session.execute(select(func.count(ReleaseDocument.id))).scalar_one()
