"""Fetch and store external news articles from configured RSS feeds."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from urllib.parse import urlparse

import feedparser
import requests

from ..config import AppConfig
from ..embeddings import EmbeddingService
from ..entity_extraction import EntityCanonicalizer, EntityExtractionService
from ..entity_extraction.store import EntityStore
from ..db import Database
from ..search import HybridSearchService
from ..observability import record_rss_fetch_metrics
from ..observability_news import record_news_ingestion_metrics
from ..utils import parse_datetime
from .articles import ArticleInput, NewsArticleRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NewsIngestResult:
    """Simple stats for news article sync runs."""

    total_feeds: int
    articles_seen: int
    inserted: int
    updated: int


class NewsIngestor:
    """Fetch RSS feeds and persist article metadata for cross linking."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.database = Database(config)
        self.database.create_all()
        self.repository = NewsArticleRepository(self.database)
        self.embedding_service = EmbeddingService(config, self.database)
        self.search_service: HybridSearchService | None = None
        try:
            self.search_service = HybridSearchService(config, self.database, self.embedding_service)
        except Exception:
            logger.exception("Hybrid search unavailable for news ingestor")
        self.session = requests.Session()
        self.retention_days = config.crosslink.retention_days
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
                logger.exception("Entity extraction disabled for news ingestion")
                self.entity_service = None

    def run(self) -> NewsIngestResult:
        feeds = self.config.crosslink.feeds
        inserted = updated = 0
        seen = 0
        pruned = 0
        status = "completed"
        started = perf_counter()

        try:
            for feed_url in feeds:
                logger.info("Fetching external feed %s", feed_url)
                feed_start = perf_counter()
                try:
                    response = self.session.get(feed_url, timeout=30)
                    response.raise_for_status()
                    record_rss_fetch_metrics(
                        feed_url,
                        str(response.status_code),
                        duration_seconds=perf_counter() - feed_start,
                    )
                except requests.RequestException as exc:
                    logger.warning("Failed to fetch %s: %s", feed_url, exc)
                    record_rss_fetch_metrics(
                        feed_url,
                        "error",
                        duration_seconds=perf_counter() - feed_start,
                    )
                    continue

                parsed = feedparser.parse(response.content)
                source_name = parsed.feed.get("title") or urlparse(feed_url).netloc
                for entry in parsed.entries:
                    seen += 1
                    article = self._build_article(entry, source_name)
                    if not article:
                        continue
                record, was_inserted = self.repository.upsert(article)
                if was_inserted:
                    inserted += 1
                else:
                    updated += 1
                self._run_entity_extraction(record)
                indexed = False
                if self.search_service:
                    try:
                        self.search_service.index_article(record)
                        indexed = True
                    except Exception:
                        logger.exception("Failed to index article %s", record.id)
                if not indexed and (record.text_clean or record.summary):
                    self.embedding_service.ensure_embedding(
                        doc_type="article",
                        document_id=record.id,
                        text=record.text_clean or record.summary or "",
                    )

            logger.info(
                "News ingest complete feeds=%s seen=%s inserted=%s updated=%s",
                len(feeds),
                seen,
                inserted,
                updated,
            )
            pruned = self.repository.prune(self.retention_days)
            if pruned:
                logger.info("Pruned %s stale news articles older than %s days", pruned, self.retention_days)
            return NewsIngestResult(total_feeds=len(feeds), articles_seen=seen, inserted=inserted, updated=updated)
        except Exception:
            status = "failed"
            logger.exception("News ingest failed")
            raise
        finally:
            duration = perf_counter() - started
            article_total = None
            try:
                article_total = self.repository.count_articles()
            except Exception:
                logger.warning("Unable to compute news article count for metrics", exc_info=True)
            record_news_ingestion_metrics(
                status=status,
                seen=seen,
                inserted=inserted,
                updated=updated,
                pruned=pruned if status == "completed" else 0,
                duration_seconds=duration,
                article_total=article_total,
            )

    def _run_entity_extraction(self, record) -> None:
        if not self.entity_service or not self.entity_store:
            return
        text = (record.text_clean or record.summary or "").strip()
        if not text:
            return
        result = self.entity_service.extract(text, record.id, "article")
        if result.skipped or not result.entities:
            return
        self.entity_store.persist(record.id, "article", text, result.entities)

    def _build_article(self, entry: dict, source_name: str) -> ArticleInput | None:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            return None

        published = parse_datetime(entry.get("published") or entry.get("updated"))
        summary = entry.get("summary") or entry.get("description")
        text_clean = summary

        return ArticleInput(
            title=title,
            url=link,
            source=source_name,
            summary=summary.strip() if summary else None,
            text_clean=text_clean.strip() if text_clean else None,
            published_at=published,
        )


def main() -> None:
    config = AppConfig.from_env()
    ingestor = NewsIngestor(config)
    ingestor.run()


if __name__ == "__main__":
    main()
