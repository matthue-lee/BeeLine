"""Compute retrieval quality metrics for releases/articles using labeled queries."""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from beeline_ingestor.config import AppConfig
from beeline_ingestor.db import Database
from beeline_ingestor.embeddings import EmbeddingService
from beeline_ingestor.search import HybridSearchService


def ndcg_at_k(results, relevant_ids, k):
    dcg = 0.0
    for idx, hit in enumerate(results[:k]):
        if hit["id"] in relevant_ids:
            dcg += 1.0 / (idx + 1)
    ideal = sum(1.0 / (i + 1) for i in range(min(len(relevant_ids), k)))
    return dcg / ideal if ideal else 0.0


def recall_at_k(results, relevant_ids, k):
    if not relevant_ids:
        return 0.0
    found = sum(1 for hit in results[:k] if hit["id"] in relevant_ids)
    return found / len(relevant_ids)


def main() -> None:
    dataset_path = Path("evaluation/retrieval_queries.json")
    if not dataset_path.exists():
        print("No evaluation dataset found at evaluation/retrieval_queries.json")
        return
    queries = json.loads(dataset_path.read_text())
    config = AppConfig.from_env()
    database = Database(config)
    database.create_all()
    embeddings = EmbeddingService(config, database)
    search_service = HybridSearchService(config, database, embeddings)

    release_scores = []
    article_scores = []
    release_recalls = []
    article_recalls = []

    for item in queries:
        query_text = item["query"]
        release_hits = search_service.search_releases(query_text, limit=5)
        release_scores.append(ndcg_at_k(release_hits, item.get("releases", []), 3))
        release_recalls.append(recall_at_k(release_hits, item.get("releases", []), 5))
        article_hits = search_service.search_articles(query_text, limit=5)
        article_scores.append(ndcg_at_k(article_hits, item.get("articles", []), 3))
        article_recalls.append(recall_at_k(article_hits, item.get("articles", []), 5))

    print(
        json.dumps(
            {
                "release_ndcg@3": round(mean(release_scores) if release_scores else 0.0, 3),
                "release_recall@5": round(mean(release_recalls) if release_recalls else 0.0, 3),
                "article_ndcg@3": round(mean(article_scores) if article_scores else 0.0, 3),
                "article_recall@5": round(mean(article_recalls) if article_recalls else 0.0, 3),
                "queries": len(queries),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
