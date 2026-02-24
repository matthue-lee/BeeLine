"""Shared Pydantic models describing queue payload contracts."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class IngestJobPayload(BaseModel):
    feed_url: str
    source_id: str
    triggered_by: Literal["cron", "manual", "backfill"]


class SummarizeJobPayload(BaseModel):
    release_id: str
    prompt_version_hint: Optional[str] = None
    priority: int = Field(default=0, ge=0)
    idempotency_token: str


class VerifyJobPayload(BaseModel):
    summary_id: str
    claim_batch: list[str] = Field(min_length=1)
    release_id: str
    idempotency_token: str


class EmbedJobPayload(BaseModel):
    source_type: Literal["release", "article"]
    source_id: str
    text_hash: str
    idempotency_token: str


class LinkJobPayload(BaseModel):
    release_id: str
    candidate_article_ids: list[str] = Field(min_length=1)
    idempotency_token: str


class EntityExtractJobPayload(BaseModel):
    source_type: Literal["release", "article", "summary"]
    source_id: str
    idempotency_token: str
