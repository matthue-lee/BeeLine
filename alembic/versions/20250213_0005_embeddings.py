"""Add embeddings table with pgvector support."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "20250213_0005"
down_revision = "20250212_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("doc_type", sa.String(length=32), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("embedding", Vector(dim=1536), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("doc_type", "document_id", name="uq_document_embedding"),
    )
    op.create_index(
        "idx_document_embeddings_doc_type",
        "document_embeddings",
        ["doc_type", "document_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_document_embeddings_doc_type", table_name="document_embeddings")
    op.drop_table("document_embeddings")
