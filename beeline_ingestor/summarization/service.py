"""Summarization service coordinating template selection and storage."""
from __future__ import annotations

import os
import logging
from typing import Optional

from time import perf_counter

from ..config import AppConfig
from ..costs import CostTracker
from ..db import Database
from ..models import ReleaseDocument, Summary
from ..observability import record_summary_metrics
from ..prompt_templates import PromptTemplateRepository
from ..schemas.summary import SummaryPayload
from ..llm.client import LLMClient, SummaryValidationError
from ..verification.service import VerificationService
from .cache import SummaryCache

logger = logging.getLogger(__name__)


class SummaryGenerationError(RuntimeError):
    pass


class SummaryRepository:
    def __init__(self, database: Database):
        self.database = database

    def get_by_release(self, release_id: str) -> Optional[Summary]:
        with self.database.session() as session:
            stmt = session.query(Summary).where(Summary.release_id == release_id)
            return stmt.one_or_none()

    def upsert(
        self,
        release_id: str,
        payload: SummaryPayload,
        *,
        model: str,
        prompt_version: str,
        cost_usd: float | None = None,
        tokens: int | None = None,
        raw_response: dict | None = None,
    ) -> Summary:
        with self.database.session() as session:
            summary = session.query(Summary).where(Summary.release_id == release_id).one_or_none()
            claims_payload = payload.to_dict()["claims"]
            if summary:
                summary.summary_short = payload.summary_short
                summary.summary_why_matters = payload.summary_why_matters
                summary.claims = claims_payload
                summary.model = model
                summary.prompt_version = prompt_version
                summary.cost_usd = cost_usd
                summary.tokens_used = tokens
                summary.raw_response = raw_response
            else:
                summary = Summary(
                    release_id=release_id,
                    summary_short=payload.summary_short,
                    summary_why_matters=payload.summary_why_matters,
                    claims=claims_payload,
                    model=model,
                    prompt_version=prompt_version,
                    cost_usd=cost_usd,
                    tokens_used=tokens,
                    raw_response=raw_response,
                )
                session.add(summary)
                session.flush()
            session.refresh(summary)
            return summary


def _payload_from_model(summary: Summary) -> SummaryPayload:
    data = {
        "release_id": summary.release_id,
        "summary_short": summary.summary_short,
        "summary_why_matters": summary.summary_why_matters,
        "claims": summary.claims or [],
    }
    return SummaryPayload.from_dict(data)


class SummaryService:
    def __init__(self, config: AppConfig, database: Database):
        self.database = database
        self.prompt_repo = PromptTemplateRepository(database)
        self.cost_tracker = CostTracker(database)
        self.llm_client = LLMClient(self.cost_tracker, model=os.getenv('SUMMARY_MODEL', 'gpt-4o-mini'))
        self.repo = SummaryRepository(database)
        ttl_seconds = int(os.getenv('SUMMARY_CACHE_TTL', '86400'))
        self.cache = SummaryCache(ttl_seconds=ttl_seconds)
        self.verification_service = VerificationService(config, database, llm_client=self.llm_client)

    def generate_if_needed(self, document: ReleaseDocument, *, skip_verification: bool = False) -> Optional[Summary]:
        start = perf_counter()
        existing = self.repo.get_by_release(document.id)
        if existing:
            if not self.cache.get(document.id):
                try:
                    self.cache.set(document.id, _payload_from_model(existing))
                except ValueError:
                    pass
            record_summary_metrics("cache_hit", duration_seconds=perf_counter() - start)
            return existing
        if not document.text_clean:
            record_summary_metrics("skipped_no_text", duration_seconds=perf_counter() - start)
            return None
        template = self.prompt_repo.choose_active('summarize')
        metadata = {
            'title': document.title,
            'published_at': document.published_at.isoformat() if document.published_at else '',
            'categories': ', '.join(document.categories or [])
        }
        try:
            result = self.llm_client.summarize(
                template=template,
                release_id=document.id,
                release_text=document.text_clean,
                metadata=metadata,
            )
        except SummaryValidationError as exc:
            record_summary_metrics("failed", duration_seconds=perf_counter() - start)
            raise SummaryGenerationError(str(exc)) from exc
        summary = self.repo.upsert(
            release_id=document.id,
            payload=result.payload,
            model=self.llm_client.model,
            prompt_version=template.version,
            cost_usd=result.cost_usd,
            tokens=result.total_tokens,
            raw_response=result.raw_response,
        )
        self.cache.invalidate(document.id)
        self.cache.set(document.id, result.payload)
        if not skip_verification:
            try:
                self.verification_service.process_summary(document, summary, result.payload)
            except Exception:  # pragma: no cover - verification failures shouldn't crash summarization
                logger.exception("Verification pipeline failed for release %s", document.id)
        record_summary_metrics("success", duration_seconds=perf_counter() - start)
        return summary
