"""Persistence helpers for external news articles and release links."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from sqlalchemy import delete, select

from ..db import Database
from ..models import NewsArticle, ReleaseArticleLink
from ..utils import compute_canonical_id


@dataclass(slots=True)
class ArticleInput:
    """Dataclass representing article fields parsed from feeds."""

    title: str
    url: str
    source: str
    summary: str | None
    text_clean: str | None
    published_at: object | None


class NewsArticleRepository:
    """Repository abstraction for news articles and release links."""

    def __init__(self, database: Database):
        self.database = database

    def upsert(self, article_input: ArticleInput) -> tuple[NewsArticle, bool]:
        """Insert or update a news article row, returning the record and insertion flag."""

        article_id = compute_canonical_id(article_input.title, article_input.url)
        text_clean = article_input.text_clean or article_input.summary or ""
        word_count = len(text_clean.split()) if text_clean else None

        with self.database.session() as session:
            existing = session.get(NewsArticle, article_id)
            if existing is None:
                existing = (
                    session.execute(select(NewsArticle).where(NewsArticle.url == article_input.url)).scalar_one_or_none()
                )
                if existing:
                    article_id = existing.id
            if existing:
                existing.title = article_input.title
                existing.url = article_input.url
                existing.source = article_input.source
                existing.summary = article_input.summary
                existing.text_clean = text_clean or existing.text_clean
                existing.word_count = word_count or existing.word_count
                existing.published_at = article_input.published_at or existing.published_at
                session.add(existing)
                return existing, False

            record = NewsArticle(
                id=article_id,
                title=article_input.title,
                url=article_input.url,
                source=article_input.source,
                summary=article_input.summary,
                text_clean=text_clean,
                word_count=word_count,
                published_at=article_input.published_at,
            )
            session.add(record)
            return record, True

    def recent_articles(self, limit: int) -> List[NewsArticle]:
        """Return the most recent articles up to the provided limit."""

        with self.database.session() as session:
            stmt = (
                select(NewsArticle)
                .order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.fetched_at.desc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars())

    def replace_links(self, release_id: str, links: Iterable[ReleaseArticleLink]) -> None:
        """Replace existing article links for a release with a new set."""

        with self.database.session() as session:
            session.execute(delete(ReleaseArticleLink).where(ReleaseArticleLink.release_id == release_id))
            for link in links:
                session.merge(link)

    def prune(self, retention_days: int) -> int:
        """Remove news articles older than the retention window and dangling links."""

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        with self.database.session() as session:
            stmt = select(NewsArticle.id).where(NewsArticle.published_at < cutoff)
            old_ids = [row[0] for row in session.execute(stmt).all()]
            if not old_ids:
                return 0
            session.execute(delete(ReleaseArticleLink).where(ReleaseArticleLink.article_id.in_(old_ids)))
            session.execute(delete(NewsArticle).where(NewsArticle.id.in_(old_ids)))
            return len(old_ids)
