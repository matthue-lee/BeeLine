"""Add raw_response to summaries

Revision ID: 20250212_0003
Revises: 20250209_0002
Create Date: 2025-02-12 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250212_0003'
down_revision = '20250209_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('summaries', sa.Column('raw_response', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('summaries', 'raw_response')
