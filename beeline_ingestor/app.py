"""Flask application factory for the ingestion service."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request
from sqlalchemy import select

from .config import AppConfig
from .ingestion import IngestionPipeline
from .models import NewsArticle, ReleaseArticleLink, ReleaseDocument

logger = logging.getLogger(__name__)


def create_app(config: Optional[AppConfig] = None) -> Flask:
    """Initialise and return the Flask application."""

    app = Flask(__name__)
    app_config = config or AppConfig.from_env()
    app.config["APP_CONFIG"] = app_config
    app.pipeline = IngestionPipeline(app_config)  # type: ignore[attr-defined]

    @app.route("/health", methods=["GET"])
    def health() -> Any:
        """Return a simple health check response."""

        return {"status": "ok"}

    @app.route("/ingest/run", methods=["POST"])
    def run_ingestion() -> Any:
        """Trigger an ingestion run and return aggregated metrics."""

        payload = request.get_json(silent=True) or {}
        since_iso = payload.get("since")
        since_dt = datetime.fromisoformat(since_iso) if since_iso else None
        if since_dt and since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)
        result = app.pipeline.run(since=since_dt)  # type: ignore[attr-defined]
        response: Dict[str, Any] = {
            "run_id": result.run_id,
            "total_items": result.total_items,
            "inserted": result.inserted,
            "updated": result.updated,
            "skipped": result.skipped,
            "failed": result.failed,
        }
        return jsonify(response), 202

    @app.route("/releases", methods=["GET"])
    def list_releases() -> Any:
        """Return a slice of recently ingested releases for quick inspection."""

        limit_param = request.args.get("limit", "20")
        try:
            limit = max(1, min(int(limit_param), 100))
        except ValueError:
            limit = 20

        offset_param = request.args.get("offset", "0")
        try:
            offset = max(0, int(offset_param))
        except ValueError:
            offset = 0

        with app.pipeline.database.session() as session:  # type: ignore[attr-defined]
            stmt = (
                select(ReleaseDocument)
                .order_by(ReleaseDocument.published_at.desc().nullslast(), ReleaseDocument.last_updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
            releases = session.execute(stmt).scalars().all()

            release_ids = [release.id for release in releases]
            links_map: dict[str, list[dict[str, object]]] = {rid: [] for rid in release_ids}
            if release_ids:
                link_stmt = (
                    select(ReleaseArticleLink, NewsArticle)
                    .join(NewsArticle, ReleaseArticleLink.article_id == NewsArticle.id)
                    .where(ReleaseArticleLink.release_id.in_(release_ids))
                    .order_by(ReleaseArticleLink.similarity.desc())
                )
                for link, article in session.execute(link_stmt).all():
                    links_map[link.release_id].append(
                        {
                            "article_id": article.id,
                            "title": article.title,
                            "source": article.source,
                            "url": article.url,
                            "similarity": link.similarity,
                            "rationale": link.rationale,
                        }
                    )

        payload = [
            {
                "id": release.id,
                "title": release.title,
                "url": release.url,
                "published_at": release.published_at.isoformat() if release.published_at else None,
                "minister": release.minister,
                "portfolio": release.portfolio,
                "categories": release.categories or [],
                "status": release.status.value,
                "word_count": release.word_count,
                "text_clean": release.text_clean,
                "text_raw": release.text_raw,
                "links": links_map.get(release.id, []),
            }
            for release in releases
        ]
        return jsonify({"items": payload, "limit": limit, "offset": offset})

    return app
