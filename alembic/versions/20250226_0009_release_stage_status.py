"""Add per-stage status columns to releases

Revision ID: 20250226_0009
Revises: 20250226_0008
Create Date: 2025-02-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20250226_0009"
down_revision = "20250226_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status_type = sa.String(length=16)

    op.add_column(
        "releases",
        sa.Column("summary_status", status_type, nullable=False, server_default="pending"),
    )
    op.add_column(
        "releases",
        sa.Column("verify_status", status_type, nullable=False, server_default="pending"),
    )
    op.add_column(
        "releases",
        sa.Column("embed_status", status_type, nullable=False, server_default="pending"),
    )
    op.add_column(
        "releases",
        sa.Column("link_status", status_type, nullable=False, server_default="pending"),
    )
    op.add_column(
        "releases",
        sa.Column("entity_status", status_type, nullable=False, server_default="pending"),
    )

    # Optional check constraints for valid values
    for col in [
        "summary_status",
        "verify_status",
        "embed_status",
        "link_status",
        "entity_status",
    ]:
        op.create_check_constraint(
            f"chk_{col}",
            "releases",
            sa.text(f"{col} IN ('pending','queued','running','done','failed')"),
        )


def downgrade() -> None:
    # Drop checks, then columns
    for col in [
        "summary_status",
        "verify_status",
        "embed_status",
        "link_status",
        "entity_status",
    ]:
        op.drop_constraint(f"chk_{col}", "releases", type_="check")

    op.drop_column("releases", "entity_status")
    op.drop_column("releases", "link_status")
    op.drop_column("releases", "embed_status")
    op.drop_column("releases", "verify_status")
    op.drop_column("releases", "summary_status")

