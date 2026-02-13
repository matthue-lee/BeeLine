"""Compute and persist similarity links between releases and news articles."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import List

from ..config import AppConfig
from ..db import Database
from ..models import ReleaseArticleLink, ReleaseDocument, Summary
from ..search.service import HybridSearchService
from .articles import NewsArticleRepository

WORD_RE = re.compile(r"[A-Za-z]{3,}")


class CrossLinker:
    """Score releases against stored news articles."""

    def __init__(self, database: Database, config: AppConfig, search_service: HybridSearchService | None = None):
        self.database = database
        self.repository = NewsArticleRepository(database)
        self.link_limit = config.crosslink.link_limit
        self.article_limit = config.crosslink.max_articles
        self.search_service = search_service

    def link_release(self, release: ReleaseDocument, summary: Summary | None = None) -> None:
        """Compute similarity to news articles and persist top matches."""

        if self.search_service:
            hits = self.search_service.search_articles_for_release(release, summary, limit=self.link_limit * 2)
            article_map = self.repository.get_by_ids([hit["id"] for hit in hits])
            links: list[ReleaseArticleLink] = []
            for hit in hits:
                article = article_map.get(hit["id"])
                if not article:
                    continue
                rationale = f"Hybrid score: {hit['score']:.3f}"
                links.append(
                    ReleaseArticleLink(
                        release_id=release.id,
                        article_id=article.id,
                        similarity=float(hit["score"]),
                        rationale=rationale,
                    )
                )
                if len(links) >= self.link_limit:
                    break
            if links:
                self.repository.replace_links(release.id, links)
            return

        reference_text = release.text_clean or ""
        if not reference_text.strip():
            return

        release_tokens = tokenize(reference_text)
        if not release_tokens:
            return

        articles = self.repository.recent_articles(self.article_limit)
        scored = []
        for article in articles:
            article_text = article.text_clean or article.summary or ""
            tokens = tokenize(article_text)
            if not tokens:
                continue
            score = cosine_similarity(release_tokens, tokens)
            if score <= 0:
                continue
            rationale = build_rationale(release_tokens, tokens)
            scored.append(
                ReleaseArticleLink(
                    release_id=release.id,
                    article_id=article.id,
                    similarity=score,
                    rationale=rationale,
                )
            )

        scored.sort(key=lambda link: link.similarity, reverse=True)
        top_links = scored[: self.link_limit]
        if top_links:
            self.repository.replace_links(release.id, top_links)


def tokenize(text: str) -> Counter[str]:
    tokens = WORD_RE.findall(text.lower())
    return Counter(tokens)


def cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = set(a.keys()) & set(b.keys())
    numerator = sum(a[token] * b[token] for token in intersection)
    denominator = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    if not denominator:
        return 0.0
    return numerator / denominator


def build_rationale(a: Counter[str], b: Counter[str]) -> str | None:
    overlap = sorted((set(a.keys()) & set(b.keys())))
    if not overlap:
        return None
    snippet = ", ".join(overlap[:5])
    return f"Shared terms: {snippet}"
