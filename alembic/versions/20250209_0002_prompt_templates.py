"""Add prompt templates table

Revision ID: 20250209_0002
Revises: 20250203_0001
Create Date: 2025-02-09 19:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250209_0002'
down_revision = '20250203_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == 'postgresql'
    metadata_type = postgresql.JSONB(astext_type=sa.Text()) if is_pg else sa.JSON()
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('metadata', metadata_type, nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('traffic_allocation', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        'uq_prompt_template_name_version',
        'prompt_templates',
        ['name', 'version'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_prompt_template_name_version', table_name='prompt_templates')
    op.drop_table('prompt_templates')
