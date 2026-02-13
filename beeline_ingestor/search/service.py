"""Hybrid search service combining Meilisearch BM25 with pgvector embeddings."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import meilisearch
from sqlalchemy import select

from ..config import AppConfig
from ..db import Database
from ..embeddings import EmbeddingService
from ..models import DocumentEmbedding, NewsArticle, ReleaseDocument, Summary

logger = logging.getLogger(__name__)


class HybridSearchService:
    def __init__(self, config: AppConfig, database: Database, embeddings: EmbeddingService):
        self.config = config
        self.database = database
        self.embeddings = embeddings
        meili_url = os.getenv("MEILISEARCH_URL", "http://meilisearch:7700")
        meili_key = os.getenv("MEILI_MASTER_KEY", "dev_master_key")
        self.client = meilisearch.Client(meili_url, meili_key)
        self.release_index = self.client.index("releases")
        self.article_index = self.client.index("news_articles")
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.release_index.update_settings(
            {
                "filterableAttributes": ["minister", "portfolio"],
                "searchableAttributes": ["title", "summary", "body", "minister", "portfolio"],
            }
        )
        self.article_index.update_settings(
            {
                "filterableAttributes": ["source"],
                "searchableAttributes": ["title", "summary", "body", "source"],
            }
        )

    def index_release(self, release: ReleaseDocument, summary: Optional[Summary]) -> None:
        doc = {
            "id": release.id,
            "title": release.title,
            "summary": summary.summary_short if summary else None,
            "body": release.text_clean or release.text_raw or "",
            "minister": release.minister,
            "portfolio": release.portfolio,
            "published_at": release.published_at.isoformat() if release.published_at else None,
        }
        self.release_index.add_documents([doc])
        text = doc["body"]
        if text:
            self.embeddings.ensure_embedding(doc_type="release", document_id=release.id, text=text)

    def index_article(self, article: NewsArticle) -> None:
        doc = {
            "id": article.id,
            "title": article.title,
            "summary": article.summary,
            "body": article.text_clean or article.summary or "",
            "source": article.source,
            "published_at": article.published_at.isoformat() if article.published_at else None,
        }
        self.article_index.add_documents([doc])
        text = doc["body"]
        if text:
            self.embeddings.ensure_embedding(doc_type="article", document_id=article.id, text=text)

    def search_releases(self, query: str, limit: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        bm25_hits = self._search_meili(self.release_index, query, limit, filters)
        vector_hits = self._vector_search("release", query, limit)
        return self._merge_scores(bm25_hits, vector_hits, limit)

    def search_articles(self, query: str, limit: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        bm25 = self._search_meili(self.article_index, query, limit, filters)
        vector_hits = self._vector_search("article", query, limit)
        return self._merge_scores(bm25, vector_hits, limit)

    def search_articles_for_release(
        self,
        release: ReleaseDocument,
        summary: Optional[Summary],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        query_text = summary.summary_short if summary and summary.summary_short else release.title
        reference_text = release.text_clean or summary.summary_short or release.title
        bm25_hits = self._search_meili(self.article_index, query_text, limit, None)
        vector_hits = self._vector_search("article", reference_text, limit)
        return self._merge_scores(bm25_hits, vector_hits, limit)

    def _search_meili(self, index, query: str, limit: int, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        options = {"limit": limit}
        if filters:
            meili_filters = []
            for key, value in filters.items():
                if isinstance(value, str):
                    meili_filters.append(f"{key} = '{value}'")
                elif isinstance(value, (int, float)):
                    meili_filters.append(f"{key} = {value}")
            if meili_filters:
                options["filter"] = meili_filters
        result = index.search(query, options)
        hits = result.get("hits", [])
        scored = []
        for idx, hit in enumerate(hits):
            ranking = hit.get("_rankingScore") or hit.get("score") or (1.0 / (idx + 1))
            scored.append({"id": hit["id"], "score": float(ranking)})
        return scored

    def _vector_search(self, doc_type: str, text: str, limit: int) -> List[Dict[str, Any]]:
        vector = self.embeddings.embed_text(text)
        if not vector:
            return []
        with self.database.session() as session:
            stmt = (
                select(DocumentEmbedding.document_id, 1 - DocumentEmbedding.embedding.cosine_distance(vector))
                .where(DocumentEmbedding.doc_type == doc_type)
                .order_by(DocumentEmbedding.embedding.cosine_distance(vector))
                .limit(limit)
            )
            rows = session.execute(stmt).all()
        return [{"id": row[0], "score": float(row[1])} for row in rows]

    def _merge_scores(self, bm25_hits: List[Dict[str, Any]], vector_hits: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        combined: Dict[str, Dict[str, float]] = {}
        for idx, hit in enumerate(bm25_hits):
            score = hit.get("score") or 1.0 / (idx + 1)
            combined.setdefault(hit["id"], {})["bm25"] = float(score)
        for idx, hit in enumerate(vector_hits):
            score = hit.get("score") or 1.0 / (idx + 1)
            combined.setdefault(hit["id"], {})["vector"] = float(score)

        results = []
        for doc_id, parts in combined.items():
            final_score = 0.4 * parts.get("bm25", 0.0) + 0.6 * parts.get("vector", 0.0)
            results.append({"id": doc_id, "score": final_score})
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]
