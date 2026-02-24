"""Embedding service for releases, summaries, and articles."""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal, Optional

try:  # pragma: no cover - optional dependency
    from openai import OpenAI
    from openai import APIError
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]
    APIError = Exception  # type: ignore[assignment]

from ..config import AppConfig
from ..costs import CostTracker
from ..db import Database
from ..models import DocumentEmbedding

logger = logging.getLogger(__name__)

EmbeddingDocType = Literal["release", "summary", "article"]


@dataclass(slots=True)
class EmbeddingResult:
    doc_type: str
    document_id: str
    embedding: list[float]
    model: str
    text_hash: str


class EmbeddingService:
    def __init__(self, config: AppConfig, database: Database):
        self.config = config
        self.database = database
        self.cost_tracker = CostTracker(database)
        self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        organization_id = os.getenv("OPENAI_ORGANIZATION_ID")
        project_id = os.getenv("OPENAI_PROJECT_ID")
        force_mock = os.getenv("LLM_MODE", "auto").lower() == "mock"
        self._simulate = force_mock or not api_key or OpenAI is None
        self._client: Optional[OpenAI] = None
        if not self._simulate:
            try:
                client_kwargs: dict[str, Any] = {"api_key": api_key}
                if base_url:
                    client_kwargs["base_url"] = base_url
                if organization_id:
                    client_kwargs["organization"] = organization_id
                if project_id:
                    client_kwargs["project"] = project_id
                self._client = OpenAI(**client_kwargs)
            except Exception:  # pragma: no cover
                logger.exception("Unable to initialise OpenAI client for embeddings; falling back to mock mode")
                self._simulate = True

    def ensure_embedding(
        self,
        *,
        doc_type: EmbeddingDocType,
        document_id: str,
        text: str,
        force_recompute: bool = False,
    ) -> Optional[EmbeddingResult]:
        normalized = (text or "").strip()
        if not normalized:
            return None
        # limit text length to avoid very long payloads
        normalized = normalized[:4000]
        text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        with self.database.session() as session:
            existing = (
                session.query(DocumentEmbedding)
                .where(DocumentEmbedding.doc_type == doc_type, DocumentEmbedding.document_id == document_id)
                .one_or_none()
            )
            if existing and not force_recompute and existing.text_hash == text_hash:
                return EmbeddingResult(
                    doc_type=existing.doc_type,
                    document_id=existing.document_id,
                    embedding=list(existing.embedding),
                    model=existing.model,
                    text_hash=existing.text_hash,
                )

        vector = self._generate_embedding(normalized)
        if not vector:
            return None

        with self.database.session() as session:
            obj = (
                session.query(DocumentEmbedding)
                .where(DocumentEmbedding.doc_type == doc_type, DocumentEmbedding.document_id == document_id)
                .one_or_none()
            )
            if obj:
                obj.embedding = vector
                obj.model = self.model
                obj.text_hash = text_hash
            else:
                obj = DocumentEmbedding(
                    doc_type=doc_type,
                    document_id=document_id,
                    embedding=vector,
                    model=self.model,
                    text_hash=text_hash,
                )
                session.add(obj)
            session.flush()
        return EmbeddingResult(
            doc_type=doc_type,
            document_id=document_id,
            embedding=vector,
            model=self.model,
            text_hash=text_hash,
        )

    def embed_text(self, text: str) -> Optional[list[float]]:
        normalized = (text or "").strip()
        if not normalized:
            return None
        normalized = normalized[:4000]
        return self._generate_embedding(normalized)

    def _generate_embedding(self, text: str) -> Optional[list[float]]:
        start = perf_counter()
        if self._simulate:
            # crude deterministic embedding
            vector = self._mock_embedding(text)
            latency_ms = int((perf_counter() - start) * 1000)
            self.cost_tracker.record_llm_call(
                model=self.model,
                operation="embedding",
                prompt_tokens=len(text)//4,
                completion_tokens=0,
                latency_ms=latency_ms,
            )
            return vector

        if not self._client:  # pragma: no cover - defensive
            return None
        try:
            response = self._client.embeddings.create(model=self.model, input=text)
        except APIError:
            logger.exception("Embedding request failed")
            return None
        vector = response.data[0].embedding
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", len(text) // 4)
        latency_ms = int((perf_counter() - start) * 1000)
        self.cost_tracker.record_llm_call(
            model=self.model,
            operation="embedding",
            prompt_tokens=int(prompt_tokens),
            completion_tokens=0,
            latency_ms=latency_ms,
        )
        return vector

    def _mock_embedding(self, text: str) -> list[float]:  # pragma: no cover - deterministic mock
        import random

        random.seed(hash(text) & 0xFFFFFFFF)
        return [random.random() for _ in range(1536)]
