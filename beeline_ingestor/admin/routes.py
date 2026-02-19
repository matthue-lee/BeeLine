"""Flask blueprint exposing admin authentication + data APIs."""
from __future__ import annotations

from functools import wraps
from typing import Callable, Optional

from flask import Blueprint, jsonify, request, current_app, g
from sqlalchemy import select

from ..db import Database
from ..models import AdminRole, ContentFlag, Entity, JobRun
from .auth import AdminAuthService


def create_admin_blueprint(auth_service: AdminAuthService, database: Database) -> Blueprint:
    bp = Blueprint("admin_api", __name__, url_prefix="/api/admin")

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

    def _extract_bearer_token() -> str:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return header.split(" ", 1)[1].strip()
        cookie_token = request.cookies.get("admin_session")
        return cookie_token or ""

    return bp
