"""Backfill embeddings and search indexes for existing releases and articles."""
from __future__ import annotations

from collections import defaultdict

from beeline_ingestor.config import AppConfig
from beeline_ingestor.db import Database
from beeline_ingestor.embeddings import EmbeddingService
from beeline_ingestor.models import NewsArticle, ReleaseDocument, Summary
from beeline_ingestor.search import HybridSearchService


def main() -> None:
    config = AppConfig.from_env()
    database = Database(config)
    database.create_all()
    embedding_service = EmbeddingService(config, database)
    search_service = HybridSearchService(config, database, embedding_service)

    with database.session() as session:
        releases = session.query(ReleaseDocument).all()
        summaries = session.query(Summary).all()
        summary_map = {s.release_id: s for s in summaries}
        articles = session.query(NewsArticle).all()

    for release in releases:
        summary = summary_map.get(release.id)
        search_service.index_release(release, summary)

    for article in articles:
        search_service.index_article(article)

    print(f"Indexed {len(releases)} releases and {len(articles)} articles")


if __name__ == "__main__":
    main()
