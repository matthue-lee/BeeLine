"""Add stage metadata to job tracking tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20250226_0008"
down_revision = "20250222_0007"
branch_labels = None
depends_on = None


job_stage_enum = sa.Enum(
    "ingest",
    "summarize",
    "verify",
    "embed",
    "link",
    "entity_extract",
    name="jobstage",
)


def upgrade() -> None:
    bind = op.get_bind()
    job_stage_enum.create(bind, checkfirst=True)

    op.add_column("job_runs", sa.Column("stage", job_stage_enum, nullable=True))
    op.add_column(
        "job_runs",
        sa.Column("release_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "job_runs",
        sa.Column("article_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "job_runs",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "job_runs",
        sa.Column("trigger_job_id", sa.Integer(), nullable=True),
    )

    op.create_foreign_key(
        "fk_job_runs_release_id",
        "job_runs",
        "releases",
        ["release_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_job_runs_article_id",
        "job_runs",
        "news_articles",
        ["article_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_job_runs_trigger",
        "job_runs",
        "job_runs",
        ["trigger_job_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_job_runs_stage_status",
        "job_runs",
        ["stage", "status"],
    )
    op.create_index("ix_job_runs_release_id", "job_runs", ["release_id"])

    op.add_column("failed_jobs", sa.Column("stage", job_stage_enum, nullable=True))
    op.add_column(
        "failed_jobs",
        sa.Column("release_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "failed_jobs",
        sa.Column("payload_snapshot", sa.JSON(), nullable=True),
    )
    op.add_column(
        "failed_jobs",
        sa.Column("bullmq_job_id", sa.String(length=128), nullable=True),
    )
    op.create_foreign_key(
        "fk_failed_jobs_release_id",
        "failed_jobs",
        "releases",
        ["release_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_failed_jobs_stage_failed_at",
        "failed_jobs",
        ["stage", "failed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_failed_jobs_stage_failed_at", table_name="failed_jobs")
    op.drop_constraint(
        "fk_failed_jobs_release_id", "failed_jobs", type_="foreignkey"
    )
    op.drop_column("failed_jobs", "bullmq_job_id")
    op.drop_column("failed_jobs", "payload_snapshot")
    op.drop_column("failed_jobs", "release_id")
    op.drop_column("failed_jobs", "stage")

    op.drop_index("ix_job_runs_release_id", table_name="job_runs")
    op.drop_index("ix_job_runs_stage_status", table_name="job_runs")
    op.drop_constraint("fk_job_runs_trigger", "job_runs", type_="foreignkey")
    op.drop_constraint("fk_job_runs_article_id", "job_runs", type_="foreignkey")
    op.drop_constraint("fk_job_runs_release_id", "job_runs", type_="foreignkey")
    op.drop_column("job_runs", "trigger_job_id")
    op.drop_column("job_runs", "priority")
    op.drop_column("job_runs", "article_id")
    op.drop_column("job_runs", "release_id")
    op.drop_column("job_runs", "stage")

    bind = op.get_bind()
    job_stage_enum.drop(bind, checkfirst=True)
