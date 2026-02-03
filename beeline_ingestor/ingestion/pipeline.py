"""Orchestration logic for the ingestion job."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..config import AppConfig
from ..crosslink import CrossLinker
from ..db import Database
from ..models import DocumentStatus, IngestionRun
from .cleaner import ContentCleaner
from .fetcher import ArticleFetcher
from .rss import FeedClient, FeedEntry
from .storage import ReleaseRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ItemResult:
    """Outcome of processing a single feed entry."""

    entry: FeedEntry
    status: DocumentStatus
    inserted: bool


@dataclass(slots=True)
class RunResult:
    """Aggregated metrics for one ingestion execution."""

    run_id: int
    total_items: int
    inserted: int
    updated: int
    skipped: int
    failed: int


class IngestionPipeline:
    """High-level ingestion orchestrator coordinating all stages."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.database = Database(config)
        self.database.create_all()
        self.feed_client = FeedClient(config.feeds)
        self.fetcher = ArticleFetcher(config.feeds)
        self.cleaner = ContentCleaner()
        self.repository = ReleaseRepository(self.database, config)
        self.linker = CrossLinker(self.database, config)

    def run(self, since: Optional[datetime] = None) -> RunResult:
        """Execute the ingestion pipeline and return aggregated statistics."""

        logger.info("Starting ingestion run")
        run_record = self._create_run_record()

        entries = self.feed_client.fetch(since)
        seen_ids: set[str] = set()
        inserted = updated = skipped = failed = 0

        for entry in entries:
            if entry.id in seen_ids:
                skipped += 1
                continue
            seen_ids.add(entry.id)

            fetch_result = self.fetcher.fetch(entry.url) if self.config.enable_article_fetch else None
            raw_payload = fetch_result.content if fetch_result and fetch_result.content else entry.summary
            cleaned = self.cleaner.clean(raw_payload)

            document, was_inserted = self.repository.upsert(entry, fetch_result, cleaned)

            if was_inserted:
                inserted += 1
            else:
                updated += 1

            if document.status in {DocumentStatus.FAILED_FETCH, DocumentStatus.EMPTY_PARSE}:
                failed += 1
            else:
                self.linker.link_release(document)

        total_items = len(seen_ids)
        logger.info(
            "Ingestion run complete -- total=%s inserted=%s updated=%s skipped=%s failed=%s",
            total_items,
            inserted,
            updated,
            skipped,
            failed,
        )

        self._finalise_run_record(run_record, total_items, inserted, updated, skipped, failed)
        return RunResult(
            run_id=run_record.id,
            total_items=total_items,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            failed=failed,
        )

    def _create_run_record(self) -> IngestionRun:
        """Persist a new `IngestionRun` row and return it."""

        run = IngestionRun()
        with self.database.session() as session:
            session.add(run)
            session.flush()
            session.refresh(run)
            return run

    def _finalise_run_record(
        self,
        run: IngestionRun,
        total: int,
        inserted: int,
        updated: int,
        skipped: int,
        failed: int,
    ) -> None:
        """Update the existing run record with final metrics."""

        with self.database.session() as session:
            db_run = session.get(IngestionRun, run.id)
            if not db_run:
                logger.error("Ingestion run %s missing during finalisation", run.id)
                return
            db_run.finished_at = datetime.now(timezone.utc)
            db_run.total_items = total
            db_run.inserted = inserted
            db_run.updated = updated
            db_run.skipped = skipped
            db_run.failed = failed
            db_run.details = {
                "min_content_length": self.config.min_content_length,
                "enable_article_fetch": self.config.enable_article_fetch,
            }
            session.add(db_run)
