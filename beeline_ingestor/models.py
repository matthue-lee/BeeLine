"""Database ORM models for the BeeLine ingestion service."""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Boolean,
)
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
    source: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="running")


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    superseded_by: Mapped[Optional[str]] = mapped_column(String(128), ForeignKey("releases.id"))

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
    author: Mapped[Optional[str]] = mapped_column(String)
    categories: Mapped[Optional[dict]] = mapped_column(JSON)
    language: Mapped[Optional[str]] = mapped_column(String(16))
    source_category: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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
    verified: Mapped[bool] = mapped_column(default=False)
    verification_score: Mapped[Optional[float]] = mapped_column(Float)
    link_type: Mapped[Optional[str]] = mapped_column(String(32))
    stance: Mapped[Optional[str]] = mapped_column(String(16))
    stance_confidence: Mapped[Optional[float]] = mapped_column(Float)


class Entity(Base):
    """Canonical entity record derived from releases and articles."""

    __tablename__ = "entities"
    __table_args__ = (
        Index("idx_entities_normalized", "normalized_name", "entity_type", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("entities.id"))
    info: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EntityMention(Base):
    """Individual entity mention occurrences tied to releases or articles."""

    __tablename__ = "entity_mentions"
    __table_args__ = (
        Index("idx_entity_mentions_entity", "entity_id"),
        Index("idx_entity_mentions_source", "source_type", "source_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    detector: Mapped[str] = mapped_column(String(64), nullable=False)
    context: Mapped[Optional[str]] = mapped_column(Text)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EntityAlias(Base):
    """Alternate spellings or aliases for canonical entities."""

    __tablename__ = "entity_aliases"

    entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    normalized_alias: Mapped[str] = mapped_column(String, primary_key=True)
    alias: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EntityCooccurrence(Base):
    """Pre-computed relationships between frequently paired entities."""

    __tablename__ = "entity_cooccurrences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_a_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id", ondelete="CASCADE"))
    entity_b_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id", ondelete="CASCADE"))
    cooccurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    relationship_type: Mapped[Optional[str]] = mapped_column(String(32))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EntityCooccurrenceDocument(Base):
    """Documents contributing to cooccurrence edges."""

    __tablename__ = "entity_cooccurrence_documents"

    cooccurrence_id: Mapped[int] = mapped_column(Integer, ForeignKey("entity_cooccurrences.id", ondelete="CASCADE"), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    proximity: Mapped[Optional[str]] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EntityStatistic(Base):
    """Materialized metrics powering entity dashboards."""

    __tablename__ = "entity_statistics"

    entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    mentions_total: Mapped[int] = mapped_column(Integer, default=0)
    mentions_last_7d: Mapped[int] = mapped_column(Integer, default=0)
    mentions_last_30d: Mapped[int] = mapped_column(Integer, default=0)
    top_cooccurrences: Mapped[Optional[dict]] = mapped_column(JSON)
    mentions_by_month: Mapped[Optional[dict]] = mapped_column(JSON)
    last_computed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class JobRun(Base):
    """Operational record for asynchronous jobs."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    params: Mapped[Optional[dict]] = mapped_column(JSON)
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)


class FailedJob(Base):
    """Jobs that require retries or manual intervention."""

    __tablename__ = "failed_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_runs.id", ondelete="SET NULL"))
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LLMCall(Base):
    """Token usage and cost tracking for each LLM invocation."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_runs.id", ondelete="SET NULL"))
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DailyCost(Base):
    """Roll-up table for dashboards showing spend per day."""

    __tablename__ = "daily_costs"

    date: Mapped[datetime] = mapped_column(Date, primary_key=True)
    operation: Mapped[str] = mapped_column(String(64), primary_key=True)
    total_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PromptTemplate(Base):
    """Prompt templates used for summarization/verification."""

    __tablename__ = "prompt_templates"
    __table_args__ = (
        Index("uq_prompt_template_name_version", "name", "version", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    traffic_allocation: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ContentFlag(Base):
    """Quality-control flags for manual review."""

    __tablename__ = "content_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    flag_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[Optional[str]] = mapped_column(String(16))
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    resolved: Mapped[bool] = mapped_column(default=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(64))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Summary(Base):
    """LLM-generated release summaries."""

    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_id: Mapped[str] = mapped_column(String(128), ForeignKey("releases.id", ondelete="CASCADE"), unique=True)
    summary_short: Mapped[str] = mapped_column(Text, nullable=False)
    summary_why_matters: Mapped[Optional[str]] = mapped_column(Text)
    claims: Mapped[Optional[dict]] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(16))
    verification_score: Mapped[Optional[float]] = mapped_column(Float)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
