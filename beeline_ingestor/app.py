"""Flask application factory for the ingestion service."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from flask import Flask, Response, jsonify, request
from sqlalchemy import func, select

from .config import AppConfig
from .ingestion import IngestionPipeline
from .models import DailyCost, DocumentStatus, JobRun, LLMCall, NewsArticle, ReleaseArticleLink, ReleaseDocument, Summary
from .observability import init_sentry, render_metrics

logger = logging.getLogger(__name__)


def create_app(config: Optional[AppConfig] = None) -> Flask:
    """Initialise and return the Flask application."""

    app = Flask(__name__)
    app_config = config or AppConfig.from_env()
    app.config["APP_CONFIG"] = app_config
    app.pipeline = IngestionPipeline(app_config)  # type: ignore[attr-defined]
    init_sentry(
        app_config.sentry_dsn,
        environment=app_config.sentry_environment,
        traces_sample_rate=app_config.sentry_traces_sample_rate,
        profiles_sample_rate=app_config.sentry_profiles_sample_rate,
        enable_flask_integration=True,
    )

    def parse_iso_param(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @app.route("/health", methods=["GET"])
    def health() -> Any:
        """Return a simple health check response."""

        return {"status": "ok"}

    @app.route("/metrics", methods=["GET"])
    def metrics() -> Response:
        """Expose Prometheus metrics collected within the app."""

        payload, content_type = render_metrics()
        return Response(payload, mimetype=content_type)

    @app.route("/ingest/run", methods=["POST"])
    def run_ingestion() -> Any:
        """Trigger an ingestion run and return aggregated metrics."""

        payload = request.get_json(silent=True) or {}
        since_iso = payload.get("since")
        since_dt = datetime.fromisoformat(since_iso) if since_iso else None
        if since_dt and since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)
        until_iso = payload.get("until")
        until_dt = datetime.fromisoformat(until_iso) if until_iso else None
        if until_dt and until_dt.tzinfo is None:
            until_dt = until_dt.replace(tzinfo=timezone.utc)
        limit = payload.get("limit")
        limit_value = int(limit) if isinstance(limit, (int, str)) and str(limit).isdigit() else None
        result = app.pipeline.run(since=since_dt, until=until_dt, limit=limit_value)  # type: ignore[attr-defined]
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

        minister_filter = request.args.get("minister")
        portfolio_filter = request.args.get("portfolio")
        status_filter = request.args.get("status")
        date_from = parse_iso_param(request.args.get("date_from"))
        date_to = parse_iso_param(request.args.get("date_to"))

        with app.pipeline.database.session() as session:  # type: ignore[attr-defined]
            stmt = (
                select(ReleaseDocument)
                .order_by(ReleaseDocument.published_at.desc().nullslast(), ReleaseDocument.last_updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
            if minister_filter:
                stmt = stmt.where(ReleaseDocument.minister == minister_filter)
            if portfolio_filter:
                stmt = stmt.where(ReleaseDocument.portfolio == portfolio_filter)
            if date_from:
                stmt = stmt.where(ReleaseDocument.published_at >= date_from)
            if date_to:
                stmt = stmt.where(ReleaseDocument.published_at <= date_to)
            if status_filter:
                try:
                    stmt = stmt.where(ReleaseDocument.status == DocumentStatus(status_filter))
                except ValueError:
                    logger.warning("Invalid status filter '%s'", status_filter)

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
            summary_map: dict[str, Summary] = {}
            if release_ids:
                summary_stmt = select(Summary).where(Summary.release_id.in_(release_ids))
                for summary in session.execute(summary_stmt).scalars().all():
                    summary_map[summary.release_id] = summary

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
                "summary": _serialize_summary(summary_map.get(release.id)),
            }
            for release in releases
        ]
        return jsonify({"items": payload, "limit": limit, "offset": offset})

    @app.route("/jobs", methods=["GET"])
    def list_jobs() -> Any:
        """Return recent job run metadata for debugging."""

        try:
            limit = max(1, min(int(request.args.get("limit", "50")), 200))
        except ValueError:
            limit = 50

        job_type_filter = request.args.get("job_type")
        status_filter = request.args.get("status")

        with app.pipeline.database.session() as session:  # type: ignore[attr-defined]
            stmt = select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
            if job_type_filter:
                stmt = stmt.where(JobRun.job_type == job_type_filter)
            if status_filter:
                stmt = stmt.where(JobRun.status == status_filter)
            job_rows = session.execute(stmt).scalars().all()

        items = [
            {
                "id": job.id,
                "job_type": job.job_type,
                "status": job.status,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "duration_ms": job.duration_ms,
                "error": job.error_message,
            }
            for job in job_rows
        ]
        return jsonify({"items": items, "count": len(items)})

    @app.route("/costs", methods=["GET"])
    def cost_report() -> Any:
        """Return aggregated cost metrics over the requested time window."""

        try:
            hours = max(1, min(int(request.args.get("hours", "24")), 24 * 30))
        except ValueError:
            hours = 24
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        with app.pipeline.database.session() as session:  # type: ignore[attr-defined]
            agg_stmt = (
                select(
                    LLMCall.operation,
                    LLMCall.model,
                    func.count().label("calls"),
                    func.sum(LLMCall.total_tokens).label("tokens"),
                    func.sum(LLMCall.cost_usd).label("cost_usd"),
                )
                .where(LLMCall.created_at >= since)
                .group_by(LLMCall.operation, LLMCall.model)
                .order_by(LLMCall.operation)
            )
            aggregates = session.execute(agg_stmt).all()

            daily_stmt = select(DailyCost).order_by(DailyCost.date.desc()).limit(14)
            daily_rows = session.execute(daily_stmt).scalars().all()

        payload = {
            "hours": hours,
            "since": since.isoformat(),
            "aggregates": [
                {
                    "operation": row.operation,
                    "model": row.model,
                    "calls": row.calls or 0,
                    "tokens": int(row.tokens or 0),
                    "cost_usd": float(row.cost_usd or 0),
                }
                for row in aggregates
            ],
            "daily_totals": [
                {
                    "date": daily.date.isoformat(),
                    "operation": daily.operation,
                    "total_calls": daily.total_calls,
                    "total_tokens": daily.total_tokens,
                    "total_cost_usd": daily.total_cost_usd,
                }
                for daily in daily_rows
            ],
        }
        return jsonify(payload)

    return app


def _serialize_summary(summary: Summary | None) -> Any:
    if not summary:
        return None
    return {
        "summary_short": summary.summary_short,
        "summary_why_matters": summary.summary_why_matters,
        "claims": summary.claims or [],
        "model": summary.model,
        "prompt_version": summary.prompt_version,
        "verification_score": summary.verification_score,
        "cost_usd": summary.cost_usd,
        "tokens_used": summary.tokens_used,
        "raw_response": summary.raw_response,
    }
