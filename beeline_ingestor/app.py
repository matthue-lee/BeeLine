"""Flask application factory for the ingestion service."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request

from .config import AppConfig
from .ingestion import IngestionPipeline

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

    return app
