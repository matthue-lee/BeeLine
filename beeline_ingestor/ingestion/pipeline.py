"""Orchestration logic for the ingestion job."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
import os
import hashlib
from typing import Optional

from ..config import AppConfig
from ..crosslink import CrossLinker
from ..db import Database
from ..embeddings import EmbeddingService
from ..entity_extraction import EntityCanonicalizer, EntityExtractionService
from ..entity_extraction.store import EntityStore
from ..models import DocumentStatus, IngestionRun, ReleaseDocument
from ..observability import record_ingestion_metrics
from ..queue_dispatcher import QueueDispatcher, make_idempotency_token
from ..search.service import HybridSearchService
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
        # Ensure tables exist in development environments; production should rely on Alembic.
        if not config.skip_create_all:
            self.database.create_all()
        self.feed_client = FeedClient(config.feeds)
        self.fetcher = ArticleFetcher(config.feeds)
        self.cleaner = ContentCleaner()
        self.repository = ReleaseRepository(self.database, config)
        self.embedding_service = EmbeddingService(config, self.database)
        self.search_service: HybridSearchService | None = None
        try:
            self.search_service = HybridSearchService(config, self.database, self.embedding_service)
        except Exception:
            logger.exception("Hybrid search initialisation failed; falling back to legacy linking")
        self.linker = CrossLinker(self.database, config, search_service=self.search_service)
        self.canonicalizer = EntityCanonicalizer(config.entity_extraction) if config.enable_entity_extraction else None
        self.entity_store = (
            EntityStore(self.database, canonicalizer=self.canonicalizer)
            if config.enable_entity_extraction
            else None
        )
        self.entity_service: EntityExtractionService | None = None
        if config.enable_entity_extraction:
            try:
                self.entity_service = EntityExtractionService(config.entity_extraction)
            except RuntimeError:
                logger.exception("Entity extraction disabled due to initialisation failure")
                self.entity_service = None
        # Queue dispatcher for decoupled stages (Week B)
        self.queue_dispatcher: QueueDispatcher | None = None
        try:
            self.queue_dispatcher = QueueDispatcher()
        except Exception:
            logger.exception("Queue dispatcher initialisation failed; dispatch disabled")
            self.queue_dispatcher = None

    def run(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = None,
        source: str = "rss",
    ) -> RunResult:
        """Execute the ingestion pipeline and return aggregated statistics."""

        start = perf_counter()
        logger.info("Starting ingestion run")
        run_record = self._create_run_record(source)

        entries = self.feed_client.fetch(since, until)
        if limit is not None:
            entries = entries[: max(limit, 0)]
        seen_ids: set[str] = set()
        inserted = updated = skipped = failed = 0
        release_total: int | None = None
        run_status = "completed"

        try:
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
                    continue

                # Decoupled stage dispatch: summarize, embed, entity_extract
                text = (document.text_clean or document.text_raw or "").strip()
                if not text:
                    skipped += 1
                    continue
                if self.queue_dispatcher:
                    try:
                        # summarize
                        sum_token = make_idempotency_token(
                            "summarize",
                            release_id=document.id,
                            prompt_version_hint=os.getenv("VERIFICATION_PROMPT_VERSION", "latest"),
                        )
                        self.queue_dispatcher.enqueue(
                            "summarize",
                            {"release_id": document.id, "idempotency_token": sum_token},
                        )
                        # embed
                        text_hash = hashlib.sha256(text.encode()).hexdigest()
                        emb_token = make_idempotency_token(
                            "embed", source_type="release", source_id=document.id, text_hash=text_hash
                        )
                        self.queue_dispatcher.enqueue(
                            "embed",
                            {
                                "source_type": "release",
                                "source_id": document.id,
                                "text_hash": text_hash,
                                "idempotency_token": emb_token,
                            },
                        )
                        # entity_extract
                        ent_token = make_idempotency_token(
                            "entity_extract", source_type="release", source_id=document.id
                        )
                        self.queue_dispatcher.enqueue(
                            "entity_extract",
                            {
                                "source_type": "release",
                                "source_id": document.id,
                                "idempotency_token": ent_token,
                            },
                        )
                        # Update stage statuses to 'queued'
                        with self.database.session() as session:
                            db_doc = session.get(ReleaseDocument, document.id)
                            if db_doc:
                                db_doc.summary_status = "queued"
                                db_doc.embed_status = "queued"
                                db_doc.entity_status = "queued"
                                session.add(db_doc)
                    except Exception:
                        logger.warning("Dispatch to queue failed for release %s", document.id, exc_info=True)

            total_items = len(seen_ids)
            logger.info(
                "Ingestion run complete -- total=%s inserted=%s updated=%s skipped=%s failed=%s",
                total_items,
                inserted,
                updated,
                skipped,
                failed,
            )

            try:
                release_total = self.repository.count_documents()
            except Exception:  # pragma: no cover - defensive metric path
                logger.exception("Unable to compute release count after run")
                release_total = None

            self._finalise_run_record(
                run_record, total_items, inserted, updated, skipped, failed, status="completed"
            )
            return RunResult(
                run_id=run_record.id,
                total_items=total_items,
                inserted=inserted,
                updated=updated,
                skipped=skipped,
                failed=failed,
            )
        except Exception:
            run_status = "failed"
            self._finalise_run_record(
                run_record,
                len(seen_ids),
                inserted,
                updated,
                skipped,
                failed,
                status="failed",
            )
            raise
        finally:
            duration = perf_counter() - start
            if release_total is None:
                try:
                    release_total = self.repository.count_documents()
                except Exception:  # pragma: no cover - defensive metric path
                    logger.exception("Unable to compute release count for metrics")
                    release_total = None
            record_ingestion_metrics(
                run_status,
                inserted=inserted,
                updated=updated,
                skipped=skipped,
                failed=failed,
                duration_seconds=duration,
                release_total=release_total,
            )

    def _create_run_record(self, source: str) -> IngestionRun:
        """Persist a new `IngestionRun` row and return it."""

        run = IngestionRun(source=source, status="running")
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
        status: str,
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
                "enable_entity_extraction": self.config.enable_entity_extraction,
            }
            db_run.status = status
            session.add(db_run)

    def _run_entity_extraction(self, document) -> None:
        if not self.entity_service or not self.entity_store:
            return
        text = (document.text_clean or document.text_raw or "").strip()
        if not text:
            return
        result = self.entity_service.extract(text, document.id, "release")
        if result.skipped or not result.entities:
            return
        self.entity_store.persist(document.id, "release", text, result.entities)

    # Inline summarization removed in Week B; downstream via queue
