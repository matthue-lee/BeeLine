"""add claims tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250212_0004'
down_revision = '20250212_0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    claims = op.create_table(
        'claims',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('summary_id', sa.Integer(), sa.ForeignKey('summaries.id', ondelete='CASCADE'), nullable=False),
        sa.Column('claim_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=True),
        sa.Column('citations', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_claims_summary', 'claims', ['summary_id'])
    op.create_index('uq_claim_summary_index', 'claims', ['summary_id', 'claim_index'], unique=True)

    op.create_table(
        'claim_verifications',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('claim_id', sa.String(length=64), sa.ForeignKey('claims.id', ondelete='CASCADE'), nullable=False),
        sa.Column('verdict', sa.String(length=32), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('evidence_sentences', sa.JSON(), nullable=True),
        sa.Column('model', sa.String(length=64), nullable=True),
        sa.Column('prompt_version', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_claim_verifications_claim', 'claim_verifications', ['claim_id'])


def downgrade() -> None:
    op.drop_index('idx_claim_verifications_claim', table_name='claim_verifications')
    op.drop_table('claim_verifications')
    op.drop_index('uq_claim_summary_index', table_name='claims')
    op.drop_index('idx_claims_summary', table_name='claims')
    op.drop_table('claims')
