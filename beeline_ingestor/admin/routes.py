"""Flask blueprint exposing admin authentication + data APIs."""
from __future__ import annotations

from functools import wraps
import hashlib
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from flask import Blueprint, jsonify, request, current_app, g
from sqlalchemy import func, select

from ..db import Database
from ..config import AppConfig
from ..models import (
    AdminRole,
    Claim,
    ClaimVerification,
    ContentFlag,
    DailyCost,
    Entity,
    EntityAlias,
    EntityCooccurrence,
    EntityMention,
    EntityStatistic,
    IngestionRun,
    JobRun,
    LLMCall,
    NewsArticle,
    ReleaseArticleLink,
    ReleaseDocument,
    Summary,
)
from .auth import AdminAuthService


RELEASE_INGEST_JOB = "release_ingest"


def create_admin_blueprint(
    auth_service: AdminAuthService,
    database: Database,
    config: AppConfig,
) -> Blueprint:
    bp = Blueprint("admin_api", __name__, url_prefix="/api/admin")
    currency = config.currency

    def require_admin(role: Optional[AdminRole] = None) -> Callable:
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapped(*args, **kwargs):
                token = _extract_bearer_token()
                try:
                    result = auth_service.validate_session(token)
                except ValueError as exc:  # pragma: no cover - defensive
                    return jsonify({"error": str(exc)}), 401
                if role == AdminRole.ADMIN and result.user.role != AdminRole.ADMIN:
                    return jsonify({"error": "forbidden"}), 403
                g.admin_user = result.user
                g.admin_session = result.session
                return func(*args, **kwargs)

            return wrapped

        return decorator

    @bp.route("/auth/request-code", methods=["POST"])
    def request_code() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or "").strip().lower()
        if not email:
            return jsonify({"error": "email_required"}), 400
        auth_service.request_code(email)
        return jsonify({"status": "sent"}), 202

    @bp.route("/auth/verify", methods=["POST"])
    def verify_code() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or "").strip().lower()
        code = (payload.get("code") or "").strip()
        if not email or not code:
            return jsonify({"error": "invalid_request"}), 400
        try:
            token, expires_at, user = auth_service.verify_code(email, code, request.remote_addr)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 401
        auth_service.record_action(user_id=user.id, action="login", context=None, ip_address=request.remote_addr)
        return (
            jsonify(
                {
                    "token": token,
                    "expires_at": expires_at.isoformat(),
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "role": user.role.value,
                        "display_name": user.display_name,
                    },
                }
            ),
            200,
        )

    @bp.route("/auth/logout", methods=["POST"])
    @require_admin()
    def logout() -> tuple[dict, int]:
        token = _extract_bearer_token()
        auth_service.revoke_token(token)
        auth_service.record_action(
            user_id=getattr(g, "admin_user", None).id if getattr(g, "admin_user", None) else None,
            action="logout",
            context=None,
            ip_address=request.remote_addr,
        )
        return jsonify({"status": "ok"}), 200

    @bp.route("/me", methods=["GET"])
    @require_admin()
    def current_user() -> dict:
        user = g.admin_user
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "display_name": user.display_name,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        }

    @bp.route("/system/overview", methods=["GET"])
    @require_admin()
    def system_overview() -> dict:
        hours = max(1, min(int(request.args.get("hours", 24)), 24 * 7))
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=hours)
        with database.session() as session:
            releases_total = session.execute(select(func.count(ReleaseDocument.id))).scalar() or 0
            releases_recent = (
                session.execute(
                    select(func.count(ReleaseDocument.id)).where(ReleaseDocument.created_at >= since)
                ).scalar()
                or 0
            )
            articles_recent = (
                session.execute(
                    select(func.count(NewsArticle.id)).where(NewsArticle.created_at >= since)
                ).scalar()
                or 0
            )
            mentions_recent = (
                session.execute(
                    select(func.count(EntityMention.id)).where(EntityMention.created_at >= since)
                ).scalar()
                or 0
            )
            flags_open = (
                session.execute(select(func.count(ContentFlag.id)).where(ContentFlag.resolved.is_(False))).scalar()
                or 0
            )
            ingestion_run = (
                session.execute(select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(1))
                .scalars()
                .first()
            )
            job_breakdown = (
                session.execute(
                    select(JobRun.job_type, JobRun.status, func.count())
                    .group_by(JobRun.job_type, JobRun.status)
                )
                .all()
            )
            recent_jobs = (
                session.execute(
                    select(JobRun).order_by(JobRun.started_at.desc()).limit(5)
                )
                .scalars()
                .all()
            )
        return {
            "since": since.isoformat(),
            "generated_at": now.isoformat(),
            "counters": {
                "releases_total": releases_total,
                "releases_last_window": releases_recent,
                "articles_last_window": articles_recent,
                "entity_mentions_last_window": mentions_recent,
                "open_flags": flags_open,
            },
            "last_ingestion": _serialize_ingestion_run(ingestion_run) if ingestion_run else None,
            "job_breakdown": [
                {"job_type": jt, "status": status, "count": count}
                for jt, status, count in job_breakdown
            ],
            "recent_jobs": [
                {
                    "id": job.id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "duration_ms": job.duration_ms,
                }
                for job in recent_jobs
            ],
        }

    @bp.route("/entities", methods=["GET"])
    @require_admin()
    def list_entities() -> dict:
        limit = min(int(request.args.get("limit", 25)), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
        entity_type = request.args.get("type")
        verified = request.args.get("verified")
        search = request.args.get("q")
        with database.session() as session:
            stmt = select(Entity).order_by(Entity.mention_count.desc()).offset(offset).limit(limit)
            if entity_type:
                stmt = stmt.where(Entity.entity_type == entity_type)
            if verified is not None:
                stmt = stmt.where(Entity.verified.is_(bool(int(verified))))
            if search:
                stmt = stmt.where(Entity.canonical_name.ilike(f"%{search}%"))
            rows = session.execute(stmt).scalars().all()
        items = [
            {
                "id": row.id,   
                "canonical_name": row.canonical_name,
                "entity_type": row.entity_type,
                "verified": row.verified,
                "mention_count": row.mention_count,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
            for row in rows
        ]
        return {"items": items, "limit": limit, "offset": offset}

    @bp.route("/entities/<entity_id>", methods=["GET"])
    @require_admin()
    def entity_detail(entity_id: str) -> tuple[dict, int]:
        with database.session() as session:
            entity = session.get(Entity, entity_id)
            if not entity:
                return jsonify({"error": "not_found"}), 404
            aliases = (
                session.execute(select(EntityAlias).where(EntityAlias.entity_id == entity_id))
                .scalars()
                .all()
            )
            stats = session.get(EntityStatistic, entity_id)
            mentions = (
                session.execute(
                    select(EntityMention)
                    .where(EntityMention.entity_id == entity_id)
                    .order_by(EntityMention.created_at.desc())
                    .limit(10)
                )
                .scalars()
                .all()
            )
            cooccurrences_a = (
                session.execute(
                    select(EntityCooccurrence, Entity)
                    .join(Entity, Entity.id == EntityCooccurrence.entity_b_id)
                    .where(EntityCooccurrence.entity_a_id == entity_id)
                    .order_by(EntityCooccurrence.cooccurrence_count.desc())
                    .limit(5)
                )
                .all()
            )
            cooccurrences_b = (
                session.execute(
                    select(EntityCooccurrence, Entity)
                    .join(Entity, Entity.id == EntityCooccurrence.entity_a_id)
                    .where(EntityCooccurrence.entity_b_id == entity_id)
                    .order_by(EntityCooccurrence.cooccurrence_count.desc())
                    .limit(5)
                )
                .all()
            )

        def _serialize_cooccurrence(row):
            record, partner = row
            return {
                "partner_id": partner.id,
                "partner_name": partner.canonical_name,
                "count": record.cooccurrence_count,
                "relationship_type": record.relationship_type,
                "last_seen": record.last_seen.isoformat() if record.last_seen else None,
            }

        cooccurrence_payload = [_serialize_cooccurrence(row) for row in cooccurrences_a]
        cooccurrence_payload.extend(_serialize_cooccurrence(row) for row in cooccurrences_b)

        return (
            jsonify(
                {
                    "entity": {
                        "id": entity.id,
                        "canonical_name": entity.canonical_name,
                        "entity_type": entity.entity_type,
                        "info": entity.info or {},
                        "verified": entity.verified,
                        "mention_count": entity.mention_count,
                        "first_seen": entity.first_seen.isoformat() if entity.first_seen else None,
                        "last_seen": entity.last_seen.isoformat() if entity.last_seen else None,
                    },
                    "aliases": [
                        {
                            "alias": alias.alias,
                            "normalized_alias": alias.normalized_alias,
                            "source": alias.source,
                            "confidence": alias.confidence,
                        }
                        for alias in aliases
                    ],
                    "statistics": {
                        "mentions_total": stats.mentions_total if stats else None,
                        "mentions_last_7d": stats.mentions_last_7d if stats else None,
                        "mentions_last_30d": stats.mentions_last_30d if stats else None,
                        "top_cooccurrences": stats.top_cooccurrences if stats else None,
                    }
                    if stats
                    else None,
                    "mentions": [
                        {
                            "id": mention.id,
                            "text": mention.text,
                            "source_type": mention.source_type,
                            "source_id": mention.source_id,
                            "detector": mention.detector,
                            "confidence": mention.confidence,
                            "created_at": mention.created_at.isoformat() if mention.created_at else None,
                        }
                        for mention in mentions
                    ],
                    "cooccurrences": cooccurrence_payload,
                }
            ),
            200,
        )

    @bp.route("/job-runs", methods=["GET"])
    @require_admin()
    def list_job_runs() -> dict:
        limit = min(int(request.args.get("limit", 50)), 200)
        with database.session() as session:
            stmt = select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
            rows = session.execute(stmt).scalars().all()
        return {
            "items": [
                {
                    "id": job.id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                    "duration_ms": job.duration_ms,
                }
                for job in rows
            ]
        }

    @bp.route("/articles", methods=["GET"])
    @require_admin()
    def list_articles() -> dict:
        limit = min(int(request.args.get("limit", 50)), 200)
        source = request.args.get("source")
        with database.session() as session:
            stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc().nullslast()).limit(limit)
            if source:
                stmt = stmt.where(NewsArticle.source == source)
            rows = session.execute(stmt).scalars().all()
        return {
            "items": [
                {
                    "id": article.id,
                    "title": article.title,
                    "source": article.source,
                    "url": article.url,
                    "published_at": article.published_at.isoformat() if article.published_at else None,
                    "summary": article.summary,
                    "word_count": article.word_count,
                }
                for article in rows
            ],
            "limit": limit,
        }

    @bp.route("/ingestion-runs", methods=["GET"])
    @require_admin()
    def list_ingestion_runs() -> dict:
        limit = min(int(request.args.get("limit", 25)), 100)
        runs = []
        with database.session() as session:
            stmt = select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
            base = session.execute(stmt).scalars().all()
            for run in base:
                release_rows = session.execute(
                    select(ReleaseDocument.id, ReleaseDocument.title)
                    .where(ReleaseDocument.created_at >= run.started_at)
                    .order_by(ReleaseDocument.created_at.desc())
                    .limit(5)
                ).all()
                payload = _serialize_ingestion_run(run) or {}
                payload["recent_releases"] = [
                    {"release_id": rid, "title": title}
                    for rid, title in release_rows
                ]
                runs.append(payload)
        return {"items": runs, "limit": limit}

    @bp.route("/releases/<release_id>/debug", methods=["GET"])
    @require_admin()
    def release_debug(release_id: str):
        with database.session() as session:
            release = session.get(ReleaseDocument, release_id)
            if not release:
                return jsonify({"error": "not_found"}), 404

            summary = session.execute(
                select(Summary).where(Summary.release_id == release.id)
            ).scalar_one_or_none()

            job_row = (
                session.execute(
                    select(JobRun)
                    .where(JobRun.job_type == RELEASE_INGEST_JOB)
                    .order_by(JobRun.started_at.desc())
                )
                .scalars()
                .first()
            )

            link_rows = (
                session.execute(
                    select(ReleaseArticleLink, NewsArticle)
                    .join(NewsArticle, ReleaseArticleLink.article_id == NewsArticle.id)
                    .where(ReleaseArticleLink.release_id == release.id)
                    .order_by(ReleaseArticleLink.similarity.desc())
                )
                .all()
            )

            release_mentions = (
                session.execute(
                    select(EntityMention, Entity)
                    .join(Entity, EntityMention.entity_id == Entity.id)
                    .where(
                        EntityMention.source_type == "release",
                        EntityMention.source_id == release.id,
                    )
                )
                .all()
            )

            article_ids = [article.id for _, article in link_rows]
            article_mentions_rows: list[tuple[EntityMention, Entity]] = []
            if article_ids:
                article_mentions_rows = (
                    session.execute(
                        select(EntityMention, Entity)
                        .join(Entity, EntityMention.entity_id == Entity.id)
                        .where(
                            EntityMention.source_type == "article",
                            EntityMention.source_id.in_(article_ids),
                        )
                    )
                    .all()
                )

            claims_debug = _build_claim_debug(session, summary)
            cross_links = _build_cross_link_payload(link_rows)
            entity_snapshot = _build_entity_snapshot(
                release_mentions,
                article_mentions_rows,
                {article.id: article for _, article in link_rows},
            )

        payload = {
            "release": _serialize_release(release),
            "ingestion": _serialize_ingest_metadata(release, job_row),
            "llm_outputs": _serialize_summary(summary, currency),
            "verification": {"claims": claims_debug},
            "entity_snapshot": entity_snapshot,
            "cross_links": cross_links,
            "fallbacks": _derive_fallback_flags(summary, claims_debug, cross_links),
        }
        return jsonify(payload)

    @bp.route("/flags", methods=["GET"])
    @require_admin()
    def list_flags() -> dict:
        limit = min(int(request.args.get("limit", 50)), 200)
        only_open = request.args.get("resolved", "0") != "1"
        with database.session() as session:
            stmt = select(ContentFlag).order_by(ContentFlag.created_at.desc()).limit(limit)
            if only_open:
                stmt = stmt.where(ContentFlag.resolved.is_(False))
            rows = session.execute(stmt).scalars().all()
        items = [
            {
                "id": flag.id,
                "source_type": flag.source_type,
                "source_id": flag.source_id,
                "flag_type": flag.flag_type,
                "severity": flag.severity,
                "resolved": flag.resolved,
                "created_at": flag.created_at.isoformat() if flag.created_at else None,
            }
            for flag in rows
        ]
        return {"items": items}

    @bp.route("/flags/<int:flag_id>/resolve", methods=["POST"])
    @require_admin()
    def resolve_flag(flag_id: int) -> tuple[dict, int]:
        body = request.get_json(silent=True) or {}
        with database.session() as session:
            flag = session.get(ContentFlag, flag_id)
            if not flag:
                return jsonify({"error": "not_found"}), 404
            if flag.resolved:
                return jsonify({"status": "already_resolved"}), 200
            flag.resolved = True
            flag.resolved_at = g.admin_session.last_seen_at
            flag.resolved_by = g.admin_user.email
            session.add(flag)
        auth_service.record_action(
            user_id=g.admin_user.id,
            action="resolve_flag",
            context={"flag_id": flag_id, "notes": body.get("notes")},
            ip_address=request.remote_addr,
        )
        return jsonify({"status": "ok"}), 200

    @bp.route("/costs/summary", methods=["GET"])
    @require_admin()
    def costs_summary() -> dict:
        hours = max(1, min(int(request.args.get("hours", 24)), 24 * 30))
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        with database.session() as session:
            aggregates = (
                session.execute(
                    select(
                        LLMCall.operation,
                        LLMCall.model,
                        func.count().label("calls"),
                        func.sum(LLMCall.total_tokens).label("tokens"),
                        func.sum(LLMCall.cost_usd).label("cost_usd"),
                    )
                    .where(LLMCall.created_at >= since)
                    .group_by(LLMCall.operation, LLMCall.model)
                )
                .all()
            )
            daily_totals = (
                session.execute(select(DailyCost).order_by(DailyCost.date.desc()).limit(30))
                .scalars()
                .all()
            )
        return {
            "hours": hours,
            "since": since.isoformat(),
            "currency": currency.code,
            "aggregates": [
                {
                    "operation": row.operation,
                    "model": row.model,
                    "calls": row.calls or 0,
                    "tokens": int(row.tokens or 0),
                    "cost_usd": float(row.cost_usd or 0.0),
                    "cost_local": _cost_local(float(row.cost_usd or 0.0), currency),
                }
                for row in aggregates
            ],
            "daily_totals": [
                {
                    "date": item.date.isoformat(),
                    "operation": item.operation,
                    "total_calls": item.total_calls,
                    "total_tokens": item.total_tokens,
                    "total_cost_usd": item.total_cost_usd,
                    "total_cost_local": _cost_local(item.total_cost_usd, currency),
                }
                for item in daily_totals
            ],
        }

    @bp.route("/llm-calls", methods=["GET"])
    @require_admin()
    def list_llm_calls() -> dict:
        limit = min(int(request.args.get("limit", 50)), 200)
        with database.session() as session:
            rows = (
                session.execute(select(LLMCall).order_by(LLMCall.created_at.desc()).limit(limit))
                .scalars()
                .all()
            )
            summary_map: dict[int, Summary] = {}
            summary_ids = [call.summary_id for call in rows if getattr(call, "summary_id", None)]
            if summary_ids:
                stmt = select(Summary).where(Summary.id.in_(summary_ids))
                for summary in session.execute(stmt).scalars():
                    summary_map[summary.id] = summary
        return {
            "items": [
                {
                    "id": call.id,
                    "operation": call.operation,
                    "model": call.model,
                    "prompt_tokens": call.prompt_tokens,
                    "completion_tokens": call.completion_tokens,
                    "total_tokens": call.total_tokens,
                    "cost_usd": call.cost_usd,
                    "cost_local": _cost_local(call.cost_usd, currency),
                    "latency_ms": call.latency_ms,
                    "created_at": call.created_at.isoformat() if call.created_at else None,
                    "summary_input": summary_map.get(getattr(call, "summary_id", None)).metadata.get("input") if summary_map.get(getattr(call, "summary_id", None)) and summary_map.get(getattr(call, "summary_id", None)).metadata else None,
                    "summary_output": summary_map.get(getattr(call, "summary_id", None)).raw_response if summary_map.get(getattr(call, "summary_id", None)) else None,
                }
                for call in rows
            ],
            "currency": currency.code,
            "limit": limit,
        }

    @bp.route("/summaries", methods=["GET"])
    @require_admin()
    def list_summaries() -> dict:
        limit = min(int(request.args.get("limit", 20)), 100)
        with database.session() as session:
            stmt = (
                select(Summary, ReleaseDocument)
                .join(ReleaseDocument, Summary.release_id == ReleaseDocument.id)
                .order_by(Summary.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).all()
        items = [
            {
                "summary_id": summary.id,
                "release_id": release.id,
                "release_title": release.title,
                "prompt_version": summary.prompt_version,
                "model": summary.model,
                "verification_score": summary.verification_score,
                "cost_usd": summary.cost_usd,
                "cost_local": _cost_local(summary.cost_usd, currency),
                "tokens_used": summary.tokens_used,
                "created_at": summary.created_at.isoformat() if summary.created_at else None,
            }
            for summary, release in rows
        ]
        return {"items": items, "limit": limit, "currency": currency.code}

    def _extract_bearer_token() -> str:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return header.split(" ", 1)[1].strip()
        cookie_token = request.cookies.get("admin_session")
        return cookie_token or ""

    return bp


def _serialize_ingestion_run(run: IngestionRun | None) -> dict | None:
    if not run:
        return None
    return {
        "id": run.id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "status": run.status,
        "source": run.source,
        "total_items": run.total_items,
        "inserted": run.inserted,
        "updated": run.updated,
        "skipped": run.skipped,
        "failed": run.failed,
    }


def _serialize_release(release: ReleaseDocument) -> dict[str, Any]:
    return {
        "id": release.id,
        "title": release.title,
        "url": release.url,
        "published_at": _isoformat(release.published_at),
        "minister": release.minister,
        "portfolio": release.portfolio,
        "categories": release.categories or [],
        "status": release.status.value,
        "word_count": release.word_count,
        "clean_excerpt": _excerpt(release.text_clean),
        "raw_excerpt": _excerpt(release.text_raw),
        "dedupe_hash": _dedupe_hash(
            release.text_clean or release.text_raw or release.title or release.id
        ),
        "rss_metadata": release.provenance or {},
    }


def _serialize_ingest_metadata(release: ReleaseDocument, job_run: JobRun | None) -> dict[str, Any]:
    queue_latency_ms = _queue_latency_ms(release)
    job_payload: dict[str, Any] | None = None
    if job_run:
        job_payload = {
            "id": job_run.id,
            "job_type": job_run.job_type,
            "status": job_run.status,
            "started_at": _isoformat(job_run.started_at),
            "finished_at": _isoformat(job_run.finished_at),
            "duration_ms": job_run.duration_ms,
        }
    return {
        "fetched_at": _isoformat(release.fetched_at),
        "last_updated_at": _isoformat(release.last_updated_at),
        "queue_latency_ms": queue_latency_ms,
        "last_ingest_job": job_payload,
    }


def _serialize_summary(summary: Summary | None, currency) -> dict[str, Any] | None:
    if not summary:
        return None
    return {
        "model": summary.model,
        "prompt_version": summary.prompt_version,
        "tokens_used": summary.tokens_used,
        "cost_usd": summary.cost_usd,
        "cost_local": _cost_local(summary.cost_usd, currency),
        "summary": {
            "short": summary.summary_short,
            "why_it_matters": summary.summary_why_matters,
            "claims": summary.claims or [],
        },
        "raw_response": summary.raw_response,
    }


def _build_claim_debug(session, summary: Summary | None) -> list[dict[str, Any]]:
    if not summary:
        return []
    claim_rows = (
        session.execute(
            select(Claim)
            .where(Claim.summary_id == summary.id)
            .order_by(Claim.claim_index.asc())
        )
        .scalars()
        .all()
    )
    if not claim_rows:
        return []

    claim_ids = [claim.id for claim in claim_rows]
    verification_map: dict[str, ClaimVerification] = {}
    if claim_ids:
        verifications = (
            session.execute(
                select(ClaimVerification)
                .where(ClaimVerification.claim_id.in_(claim_ids))
                .order_by(ClaimVerification.created_at.desc())
            )
            .scalars()
            .all()
        )
        for verification in verifications:
            if verification.claim_id in verification_map:
                continue
            verification_map[verification.claim_id] = verification

    claims_payload = []
    for claim in claim_rows:
        verification = verification_map.get(claim.id)
        evidence_sentence = None
        evidence_index = None
        if verification and verification.evidence_sentences:
            for entry in verification.evidence_sentences:
                text = entry.get("text")
                if text:
                    evidence_sentence = text
                    evidence_index = entry.get("index")
                    break
        verdict = verification.verdict if verification else None
        fallback = verification is None or (verdict or "").lower() in {"insufficient", "skipped"}
        claims_payload.append(
            {
                "claim_id": claim.id,
                "index": claim.claim_index,
                "text": claim.text,
                "citations": claim.citations or [],
                "category": claim.category,
                "verification": {
                    "verdict": verdict,
                    "confidence": verification.confidence if verification else None,
                    "supporting_sentence": evidence_sentence,
                    "supporting_index": evidence_index,
                    "fallback": fallback,
                },
            }
        )
    return claims_payload


def _build_cross_link_payload(
    link_rows: list[tuple[ReleaseArticleLink, NewsArticle]]
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for link, article in link_rows:
        bm25_score, embedding_score = _parse_rationale_scores(link.rationale or "")
        snippet = _extract_snippet(article.text_clean or article.summary or "")
        payload.append(
            {
                "article_id": article.id,
                "title": article.title,
                "source": article.source,
                "url": article.url,
                "published_at": _isoformat(article.published_at),
                "bm25_score": bm25_score,
                "embedding_score": embedding_score,
                "hybrid_score": link.similarity,
                "stance": link.stance,
                "stance_confidence": link.stance_confidence,
                "snippet": snippet,
                "cache_only": link.link_type == "cache_only",
            }
        )
    return payload


def _build_entity_snapshot(
    release_rows: list[tuple[EntityMention, Entity]],
    article_rows: list[tuple[EntityMention, Entity]],
    article_lookup: dict[str, NewsArticle],
) -> dict[str, Any]:
    release_entities = _top_entities(release_rows)
    grouped: dict[str, list[tuple[EntityMention, Entity]]] = defaultdict(list)
    for mention, entity in article_rows:
        grouped[mention.source_id].append((mention, entity))
    article_entities = []
    for article_id, rows in grouped.items():
        article = article_lookup.get(article_id)
        article_entities.append(
            {
                "article_id": article_id,
                "title": article.title if article else None,
                "entities": _top_entities(rows),
            }
        )
    article_entities.sort(key=lambda item: item.get("title") or "")
    return {
        "release": release_entities,
        "articles": article_entities,
    }


def _top_entities(rows: list[tuple[EntityMention, Entity]], limit: int = 3) -> list[dict[str, Any]]:
    if not rows:
        return []
    stats: dict[str, dict[str, Any]] = {}
    for mention, entity in rows:
        bucket = stats.setdefault(
            entity.id,
            {
                "entity": entity,
                "count": 0,
                "confidence": -1.0,
                "span_text": mention.text,
                "detector": mention.detector,
            },
        )
        bucket["count"] += 1
        confidence = mention.confidence or 0.0
        if confidence > bucket["confidence"]:
            bucket["confidence"] = confidence
            bucket["span_text"] = mention.text
            bucket["detector"] = mention.detector
    ordered = sorted(
        stats.values(),
        key=lambda item: (item["count"], item["confidence"]),
        reverse=True,
    )
    result: list[dict[str, Any]] = []
    for item in ordered[:limit]:
        entity = item["entity"]
        result.append(
            {
                "entity_id": entity.id,
                "canonical_name": entity.canonical_name,
                "entity_type": entity.entity_type,
                "mentions": item["count"],
                "span_text": item["span_text"],
                "detector": item["detector"],
            }
        )
    return result


def _derive_fallback_flags(
    summary: Summary | None,
    claims: list[dict[str, Any]],
    cross_links: list[dict[str, Any]],
) -> dict[str, bool]:
    summary_model = (summary.model or "") if summary else ""
    summary_template = summary_model.lower().startswith("template") if summary_model else False
    verification_present = any(
        (claim.get("verification") or {}).get("verdict") for claim in claims
    )
    verification_skipped = bool(claims) and not verification_present
    crosslink_cache_only = bool(cross_links) and all(link.get("cache_only") for link in cross_links)
    return {
        "summary_template": summary_template,
        "verification_skipped": verification_skipped,
        "crosslink_cache_only": crosslink_cache_only,
    }


def _excerpt(text: str | None, limit: int = 600) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    truncated = stripped[:limit]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated + "…"


def _dedupe_hash(payload: str) -> str:
    digest = hashlib.sha256()
    digest.update(payload.encode("utf-8"))
    return digest.hexdigest()


def _queue_latency_ms(release: ReleaseDocument) -> int | None:
    if not release.published_at or not release.created_at:
        return None
    delta = release.created_at - release.published_at
    milliseconds = int(delta.total_seconds() * 1000)
    return max(milliseconds, 0)


def _parse_rationale_scores(text: str) -> tuple[float | None, float | None]:
    bm25_match = re.search(r"bm25\s*=\s*([0-9.]+)", text, re.IGNORECASE)
    embedding_match = re.search(r"(embedding|vector)\s*=\s*([0-9.]+)", text, re.IGNORECASE)
    bm25 = float(bm25_match.group(1)) if bm25_match else None
    embedding = float(embedding_match.group(2)) if embedding_match else None
    return bm25, embedding


def _extract_snippet(text: str, sentences: int = 2) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    segments = re.split(r"(?<=[.!?])\s+", stripped)
    trimmed = [segment.strip() for segment in segments if segment.strip()]
    if not trimmed:
        return stripped[:280]
    return " ".join(trimmed[:sentences])


def _isoformat(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _cost_local(amount: float | None, currency) -> float | None:
    if amount is None:
        return None
    return round(amount * currency.usd_to_local_rate, 4)
