"""Initial database schema for BeeLine ingestion service."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


document_status_enum = sa.Enum(
    "OK", "PARTIAL", "FAILED_FETCH", "EMPTY_PARSE", name="documentstatus"
)


revision = "20250203_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
    )

    op.create_table(
        "releases",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("minister", sa.String(), nullable=True),
        sa.Column("portfolio", sa.String(), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("text_raw", sa.Text(), nullable=True),
        sa.Column("text_clean", sa.Text(), nullable=True),
        sa.Column("status", document_status_enum, nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("superseded_by", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["superseded_by"], ["releases.id"]),
        sa.UniqueConstraint("url", name="uq_releases_url"),
    )

    op.create_table(
        "news_articles",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("text_clean", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("source_category", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("url", name="uq_news_articles_url"),
    )
    op.create_index(
        "idx_news_articles_source_published",
        "news_articles",
        ["source", "published_at"],
    )
    op.create_index("idx_news_articles_published", "news_articles", ["published_at"])

    op.create_table(
        "release_article_links",
        sa.Column("release_id", sa.String(length=128), nullable=False),
        sa.Column("article_id", sa.String(length=128), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verification_score", sa.Float(), nullable=True),
        sa.Column("link_type", sa.String(length=32), nullable=True),
        sa.Column("stance", sa.String(length=16), nullable=True),
        sa.Column("stance_confidence", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["news_articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("release_id", "article_id"),
    )
    op.create_index(
        "idx_release_article_similarity",
        "release_article_links",
        ["release_id", "similarity"],
    )

    op.create_table(
        "entities",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("canonical_name", sa.String(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("canonical_id", sa.String(length=64), nullable=True),
        sa.Column("info", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canonical_id"], ["entities.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_entities_normalized",
        "entities",
        ["normalized_name", "entity_type"],
        unique=True,
    )

    op.create_table(
        "entity_aliases",
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("normalized_alias", sa.String(), nullable=False),
        sa.Column("alias", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entity_id", "normalized_alias"),
    )

    op.create_table(
        "entity_mentions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("detector", sa.String(length=64), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_entity_mentions_entity", "entity_mentions", ["entity_id"])
    op.create_index(
        "idx_entity_mentions_source",
        "entity_mentions",
        ["source_type", "source_id"],
    )

    op.create_table(
        "entity_cooccurrences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_a_id", sa.String(length=64), nullable=False),
        sa.Column("entity_b_id", sa.String(length=64), nullable=False),
        sa.Column("cooccurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("relationship_type", sa.String(length=32), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_a_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_b_id"], ["entities.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("entity_cooccurrences")
    op.drop_index("idx_entity_mentions_source", table_name="entity_mentions")
    op.drop_index("idx_entity_mentions_entity", table_name="entity_mentions")
    op.drop_table("entity_mentions")
    op.drop_table("entity_aliases")
    op.drop_index("idx_entities_normalized", table_name="entities")
    op.drop_table("entities")
    op.drop_index("idx_release_article_similarity", table_name="release_article_links")
    op.drop_table("release_article_links")
    op.drop_index("idx_news_articles_published", table_name="news_articles")
    op.drop_index("idx_news_articles_source_published", table_name="news_articles")
    op.drop_table("news_articles")
    op.drop_table("releases")
    op.drop_table("ingestion_runs")
    document_status_enum.drop(op.get_bind(), checkfirst=True)
