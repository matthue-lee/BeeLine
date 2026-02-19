"""Add admin auth + audit tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20250213_0006"
down_revision = "20250213_0005"
branch_labels = None
depends_on = None


role_enum = sa.Enum("operator", "admin", name="adminrole")


def upgrade() -> None:
    bind = op.get_bind()
    role_enum.create(bind, checkfirst=True)

    op.create_table(
        "admin_users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=128)),
        sa.Column("role", role_enum, nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "admin_login_codes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_admin_login_codes_user", "admin_login_codes", ["user_id"])
    op.create_index("idx_admin_login_codes_expires", "admin_login_codes", ["expires_at"])

    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("ip_address", sa.String(length=64)),
    )
    op.create_index("idx_admin_sessions_token", "admin_sessions", ["token"], unique=True)
    op.create_index("idx_admin_sessions_user", "admin_sessions", ["user_id"])

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("context", sa.JSON()),
        sa.Column("ip_address", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_admin_audit_logs_user", "admin_audit_logs", ["user_id"])
    op.create_index("idx_admin_audit_logs_created", "admin_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_admin_audit_logs_created", table_name="admin_audit_logs")
    op.drop_index("idx_admin_audit_logs_user", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")

    op.drop_index("idx_admin_sessions_user", table_name="admin_sessions")
    op.drop_index("idx_admin_sessions_token", table_name="admin_sessions")
    op.drop_table("admin_sessions")

    op.drop_index("idx_admin_login_codes_expires", table_name="admin_login_codes")
    op.drop_index("idx_admin_login_codes_user", table_name="admin_login_codes")
    op.drop_table("admin_login_codes")

    op.drop_table("admin_users")
    role_enum.drop(op.get_bind(), checkfirst=True)
