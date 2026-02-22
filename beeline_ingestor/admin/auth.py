"""Admin authentication helpers (OTP + session tokens)."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select

from ..config import AdminAuthConfig
from ..db import Database
from ..models import AdminAuditLog, AdminLoginCode, AdminRole, AdminSession, AdminUser
from ..emailer import EmailSender
import logging

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionValidationResult:
    user: AdminUser
    session: AdminSession


class AdminAuthService:
    """Implements passwordless OTP login + bearer session tokens."""

    def __init__(
        self,
        config: AdminAuthConfig,
        database: Database,
        email_sender: EmailSender | None = None,
    ):
        self.config = config
        self.database = database
        self.email_sender = email_sender

    def request_code(self, email: str) -> None:
        normalized = email.strip().lower()
        with self.database.session() as session:
            user = session.execute(
                select(AdminUser).where(AdminUser.email == normalized, AdminUser.is_active.is_(True))
            ).scalar_one_or_none()
            if not user:
                logger.warning("Admin login requested for unknown or inactive user %s", normalized)
                return

            session.execute(
                delete(AdminLoginCode).where(
                    AdminLoginCode.user_id == user.id,
                    AdminLoginCode.consumed_at.is_(None),
                )
            )

            code = f"{secrets.randbelow(1_000_000):06d}"
            expires_at = datetime.now(timezone.utc) + self.config.code_ttl
            login_code = AdminLoginCode(
                user_id=user.id,
                code_hash=self._hash_code(code),
                expires_at=expires_at,
                created_at=datetime.now(timezone.utc),
            )
            session.add(login_code)

        self._deliver_code_email(normalized, code, expires_at)

    def verify_code(self, email: str, code: str, ip_address: Optional[str] = None) -> tuple[str, datetime, AdminUser]:
        normalized = email.strip().lower()
        now = datetime.now(timezone.utc)
        with self.database.session() as session:
            user = session.execute(
                select(AdminUser).where(AdminUser.email == normalized, AdminUser.is_active.is_(True))
            ).scalar_one_or_none()
            if not user:
                raise ValueError("invalid_user")

            login_code = session.execute(
                select(AdminLoginCode)
                .where(
                    AdminLoginCode.user_id == user.id,
                    AdminLoginCode.consumed_at.is_(None),
                    AdminLoginCode.expires_at >= now,
                )
                .order_by(AdminLoginCode.created_at.desc())
            ).scalar_one_or_none()
            if not login_code or login_code.code_hash != self._hash_code(code):
                raise ValueError("invalid_code")

            login_code.consumed_at = now
            user.last_login_at = now

            token = secrets.token_urlsafe(48)
            expires_at = now + self.config.session_ttl
            admin_session = AdminSession(
                user_id=user.id,
                token=token,
                expires_at=expires_at,
                last_seen_at=now,
                created_at=now,
                ip_address=ip_address,
            )
            session.add(admin_session)

            if self.config.max_sessions_per_user > 0:
                active_sessions = session.execute(
                    select(AdminSession)
                    .where(
                        AdminSession.user_id == user.id,
                        AdminSession.revoked_at.is_(None),
                    )
                    .order_by(AdminSession.created_at.desc())
                ).scalars().all()
                for stale_session in active_sessions[self.config.max_sessions_per_user :]:
                    stale_session.revoked_at = now
                    session.add(stale_session)

        return token, expires_at, user

    def validate_session(self, token: str) -> SessionValidationResult:
        if not token:
            raise ValueError("missing_token")
        now = datetime.now(timezone.utc)
        with self.database.session() as session:
            result = session.execute(
                select(AdminSession, AdminUser)
                .join(AdminUser, AdminSession.user_id == AdminUser.id)
                .where(
                    AdminSession.token == token,
                    AdminSession.revoked_at.is_(None),
                    AdminSession.expires_at >= now,
                    AdminUser.is_active.is_(True),
                )
            ).first()
            if not result:
                raise ValueError("invalid_session")
            admin_session, user = result
            if now - admin_session.last_seen_at > self.config.session_idle_timeout:
                admin_session.revoked_at = now
                raise ValueError("session_idle_timeout")
            admin_session.last_seen_at = now
            session.add(admin_session)
            return SessionValidationResult(user=user, session=admin_session)

    def revoke_token(self, token: str) -> None:
        if not token:
            return
        with self.database.session() as session:
            admin_session = session.execute(
                select(AdminSession).where(AdminSession.token == token)
            ).scalar_one_or_none()
            if admin_session and admin_session.revoked_at is None:
                admin_session.revoked_at = datetime.now(timezone.utc)
                session.add(admin_session)

    def record_action(
        self,
        user_id: Optional[str],
        action: str,
        context: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        with self.database.session() as session:
            log_entry = AdminAuditLog(
                user_id=user_id,
                action=action,
                context=context,
                ip_address=ip_address,
                created_at=datetime.now(timezone.utc),
            )
            session.add(log_entry)

    def _hash_code(self, code: str) -> str:
        digest = hashlib.sha256()
        digest.update(code.encode("utf-8"))
        return digest.hexdigest()

    def _deliver_code_email(self, email: str, code: str, expires_at: datetime) -> None:
        if self.email_sender and self.email_sender.is_configured:
            subject = "BeeLine Admin Login Code"
            body = (
                "Your BeeLine admin login code is: {code}\n\n"
                "This code expires at {expires}. If you did not request it, you can ignore this email."
            ).format(code=code, expires=expires_at.isoformat())
            self.email_sender.send(to_address=email, subject=subject, body=body)
            logger.info("Admin OTP email sent to %s", email)
        else:
            logger.warning(
                "SMTP not configured; logging admin OTP for %s (development only)",
                email,
            )
            logger.info("Admin OTP for %s: %s (expires %s)", email, code, expires_at.isoformat())
