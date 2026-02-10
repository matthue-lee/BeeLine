"""Summarization service coordinating template selection and storage."""
from __future__ import annotations

import os
from typing import Optional

from ..config import AppConfig
from ..costs import CostTracker
from ..db import Database
from ..models import ReleaseDocument, Summary
from ..prompt_templates import PromptTemplateRepository
from ..schemas.summary import SummaryPayload
from ..llm.client import LLMClient


class SummaryRepository:
    def __init__(self, database: Database):
        self.database = database

    def get_by_release(self, release_id: str) -> Optional[Summary]:
        with self.database.session() as session:
            stmt = session.query(Summary).where(Summary.release_id == release_id)
            return stmt.one_or_none()

    def upsert(self, release_id: str, payload: SummaryPayload, *, model: str, prompt_version: str, cost_usd: float | None = None, tokens: int | None = None) -> None:
        with self.database.session() as session:
            summary = session.query(Summary).where(Summary.release_id == release_id).one_or_none()
            claims_payload = payload.to_dict()['claims']
            if summary:
                summary.summary_short = payload.summary_short
                summary.summary_why_matters = payload.summary_why_matters
                summary.claims = claims_payload
                summary.model = model
                summary.prompt_version = prompt_version
                summary.cost_usd = cost_usd
                summary.tokens_used = tokens
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
                )
                session.add(summary)


class SummaryService:
    def __init__(self, config: AppConfig, database: Database):
        self.database = database
        self.prompt_repo = PromptTemplateRepository(database)
        self.cost_tracker = CostTracker(database)
        self.llm_client = LLMClient(self.cost_tracker, model=os.getenv('SUMMARY_MODEL', 'gpt-4o-mini'))
        self.repo = SummaryRepository(database)

    def generate_if_needed(self, document: ReleaseDocument) -> Optional[Summary]:
        if self.repo.get_by_release(document.id):
            return None
        if not document.text_clean:
            return None
        template = self.prompt_repo.choose_active('summarize')
        metadata = {
            'title': document.title,
            'published_at': document.published_at.isoformat() if document.published_at else '',
            'categories': ', '.join(document.categories or [])
        }
        payload = self.llm_client.summarize(
            template=template,
            release_id=document.id,
            release_text=document.text_clean,
            metadata=metadata,
        )
        self.repo.upsert(
            release_id=document.id,
            payload=payload,
            model=self.llm_client.model,
            prompt_version=template.version,
        )
        return self.repo.get_by_release(document.id)
