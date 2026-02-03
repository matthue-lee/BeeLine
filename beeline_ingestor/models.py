"""Database ORM models for the BeeLine ingestion service."""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Enum, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class DocumentStatus(str, enum.Enum):
    """Processing state for ingested documents."""

    OK = "OK"
    PARTIAL = "PARTIAL"
    FAILED_FETCH = "FAILED_FETCH"
    EMPTY_PARSE = "EMPTY_PARSE"


class IngestionRun(Base):
    """Record summarising each ingestion execution."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ReleaseDocument(Base):
    """Canonical record for a Beehive release."""

    __tablename__ = "releases"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    minister: Mapped[Optional[str]] = mapped_column(String)
    portfolio: Mapped[Optional[str]] = mapped_column(String)
    categories: Mapped[Optional[list[str]]] = mapped_column(JSON, default=list)
    text_raw: Mapped[Optional[str]] = mapped_column(Text)
    text_clean: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.PARTIAL)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)

    def has_meaningful_content(self, min_length: int) -> bool:
        """Return True when the cleaned text is long enough for downstream processing."""

        if not self.text_clean:
            return False
        return len(self.text_clean.strip()) >= min_length


class NewsArticle(Base):
    """External news article metadata for cross-source linking."""

    __tablename__ = "news_articles"
    __table_args__ = (
        Index("idx_news_articles_source_published", "source", "published_at"),
        Index("idx_news_articles_published", "published_at"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    text_clean: Mapped[Optional[str]] = mapped_column(Text)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReleaseArticleLink(Base):
    """Similarity edges between releases and news articles."""

    __tablename__ = "release_article_links"
    __table_args__ = (
        Index("idx_release_article_similarity", "release_id", "similarity"),
    )

    release_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    article_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
