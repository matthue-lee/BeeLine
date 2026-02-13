"""Claim verification orchestration."""
from __future__ import annotations

import logging
import os
from time import perf_counter
from typing import List

from ..config import AppConfig
from ..costs import CostTracker
from ..db import Database
from ..models import Claim, ClaimVerification, ContentFlag, ReleaseDocument, Summary
from ..observability import record_claim_verification_metrics
from ..schemas.summary import SummaryPayload
from ..llm.client import LLMClient, SummaryValidationError
from .claims import ClaimService
from .retrieval import EvidenceRetriever

logger = logging.getLogger(__name__)


class VerificationService:
    """Extract claims, retrieve evidence, and store verification verdicts."""

    def __init__(self, config: AppConfig, database: Database, llm_client: LLMClient | None = None):
        self.database = database
        self.claim_service = ClaimService(database)
        self.retriever = EvidenceRetriever(max_sentences=5)
        self.llm_client = llm_client or LLMClient(CostTracker(database))
        self.config = config
        self.verification_prompt_version = os.getenv('VERIFICATION_PROMPT_VERSION', 'v1')
        self.verification_system_prompt = os.getenv('VERIFICATION_SYSTEM_PROMPT')

    def process_summary(self, document: ReleaseDocument, summary: Summary, payload: SummaryPayload) -> None:
        if not document.text_clean:
            logger.warning("Skipping verification for release %s due to missing text", document.id)
            return

        claims = self.claim_service.sync_from_payload(summary, payload)
        if not claims:
            return

        for claim in claims:
            try:
                self._verify_claim(document, summary, claim)
            except SummaryValidationError:
                raise
            except Exception:  # pragma: no cover - defensive path
                logger.exception("Verification failed for claim %s", claim.id)

    def _verify_claim(self, document: ReleaseDocument, summary: Summary, claim: Claim) -> None:
        start = perf_counter()
        sentences = self.retriever.retrieve(claim.text, document.text_clean or "")
        if not sentences:
            self._persist_verification(
                claim,
                verdict="insufficient",
                confidence=0.0,
                rationale="No evidence candidates",
                evidence=[],
            )
            self._flag_claim(claim, "no_evidence", details={"claim": claim.text})
            record_claim_verification_metrics("insufficient", duration_seconds=perf_counter() - start)
            return

        metadata = {
            "release_id": document.id,
            "release_title": document.title,
            "summary_prompt": summary.prompt_version,
            "verification_prompt_version": self.verification_prompt_version,
            "verification_system_prompt": self.verification_system_prompt,
        }
        result = self.llm_client.verify_claim(
            claim_text=claim.text,
            sentences=[{"index": s.sentence_index, "text": s.text} for s in sentences],
            metadata=metadata,
        )
        self._persist_verification(
            claim,
            verdict=result.verdict,
            confidence=result.confidence,
            rationale=result.rationale,
            evidence=result.evidence,
            model=result.model,
            prompt_version=result.prompt_version,
        )
        if result.verdict != "supported":
            self._flag_claim(
                claim,
                flag_type="claim_verification_failed",
                details={
                    "verdict": result.verdict,
                    "confidence": result.confidence,
                    "claim": claim.text,
                },
            )
        record_claim_verification_metrics(result.verdict, duration_seconds=perf_counter() - start)

    def _persist_verification(
        self,
        claim: Claim,
        *,
        verdict: str,
        confidence: float | None,
        rationale: str | None,
        evidence: List[dict],
        model: str | None = None,
        prompt_version: str | None = None,
    ) -> None:
        with self.database.session() as session:
            verification = ClaimVerification(
                claim_id=claim.id,
                verdict=verdict,
                confidence=confidence,
                rationale=rationale,
                evidence_sentences=evidence,
                model=model,
                prompt_version=prompt_version,
            )
            session.add(verification)

    def _flag_claim(self, claim: Claim, flag_type: str, *, details: dict | None = None) -> None:
        with self.database.session() as session:
            flag = ContentFlag(
                source_type="claim",
                source_id=claim.id,
                flag_type=flag_type,
                severity="warning",
                details=details,
            )
            session.add(flag)
