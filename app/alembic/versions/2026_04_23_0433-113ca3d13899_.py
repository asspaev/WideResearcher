"""empty message

Revision ID: 113ca3d13899
Revises:
Create Date: 2026-04-23 04:33:49.410062

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "113ca3d13899"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "scrapped_pages",
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("page_raw_content", sa.Text(), nullable=False),
        sa.Column("page_clean_content", sa.Text(), nullable=True),
        sa.Column(
            "page_scrapped_status",
            postgresql.ENUM("SUCCESS", "IN_PROGRESS", "ERROR", name="scrape_status_enum"),
            nullable=False,
        ),
        sa.Column("meta_created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta_updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("page_url", name=op.f("pk_scrapped_pages")),
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_login", sa.String(length=32), nullable=False),
        sa.Column("user_password_hash", sa.LargeBinary(), nullable=False),
        sa.Column("meta_created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta_updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_users")),
        sa.UniqueConstraint("user_login", name=op.f("uq_users_user_login")),
    )
    op.create_table(
        "models",
        sa.Column("model_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("model_type", sa.String(length=50), nullable=False),
        sa.Column("model_key_api", sa.Text(), nullable=True),
        sa.Column("model_base_url", sa.Text(), nullable=False),
        sa.Column("model_api_model", sa.Text(), nullable=False),
        sa.Column("model_max_tokens", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta_created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta_updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name=op.f("fk_models_user_id_users")),
        sa.PrimaryKeyConstraint("model_id", name=op.f("pk_models")),
    )
    op.create_table(
        "researches",
        sa.Column("research_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("research_parent_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "research_status",
            postgresql.ENUM("IN_PROCESS", "COMPLETE", "ERROR", name="research_status_enum"),
            nullable=False,
        ),
        sa.Column("research_stage", sa.Text(), nullable=False),
        sa.Column("research_name", sa.Text(), nullable=False),
        sa.Column("research_version_name", sa.Text(), nullable=False),
        sa.Column("research_body_start", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_body_finish", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("research_direction_content", sa.Text(), nullable=True),
        sa.Column("research_search_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_result_search_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_result_bm25_chunks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_result_embed_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_result_embed_chunks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_result_rerank_chunks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_error_body", sa.Text(), nullable=True),
        sa.Column("settings_search_areas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("settings_exclude_search_areas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("settings_n_async_parse", sa.Integer(), server_default="3", nullable=False),
        sa.Column("settings_scenario_type", sa.Text(), server_default="normal", nullable=False),
        sa.Column("settings_n_vectors", sa.Integer(), server_default="5", nullable=False),
        sa.Column("settings_n_search_queries", sa.Integer(), server_default="5", nullable=False),
        sa.Column("settings_n_top_search_results", sa.Integer(), server_default="10", nullable=False),
        sa.Column("settings_n_top_bm25_chunks", sa.Integer(), server_default="50", nullable=False),
        sa.Column("settings_n_top_embed_chunks", sa.Integer(), server_default="30", nullable=False),
        sa.Column("settings_n_top_rerank_chunks", sa.Integer(), server_default="15", nullable=False),
        sa.Column("settings_n_top_chunks", sa.Integer(), server_default="10", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_id_answer", sa.BigInteger(), nullable=False),
        sa.Column("model_id_search", sa.BigInteger(), nullable=False),
        sa.Column("model_id_direction", sa.BigInteger(), nullable=True),
        sa.Column("model_id_embed", sa.BigInteger(), nullable=True),
        sa.Column("model_id_reranker", sa.BigInteger(), nullable=True),
        sa.Column("meta_created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta_updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_parent_id"], ["researches.research_id"], name=op.f("fk_researches_research_parent_id_researches")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name=op.f("fk_researches_user_id_users")),
        sa.PrimaryKeyConstraint("research_id", name=op.f("pk_researches")),
    )
    op.create_table(
        "user_notifications",
        sa.Column("notification_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("notification_title", sa.Text(), nullable=True),
        sa.Column("notification_subtitle", sa.Text(), nullable=True),
        sa.Column(
            "notification_status",
            postgresql.ENUM("UNCHECKED", "CHECKED", name="notification_status_enum"),
            nullable=False,
        ),
        sa.Column("notification_link", sa.Text(), nullable=True),
        sa.Column("meta_created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta_updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(notification_title IS NOT NULL OR notification_subtitle IS NOT NULL)",
            name=op.f("ck_user_notifications_ck_notification_title_or_subtitle_not_null"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name=op.f("fk_user_notifications_user_id_users")),
        sa.PrimaryKeyConstraint("notification_id", name=op.f("pk_user_notifications")),
    )
    op.create_table(
        "chunk_summaries",
        sa.Column("chunk_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("research_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_content", sa.Text(), nullable=False),
        sa.Column("bm25_score", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("embed_score", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("rerank_score", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("page_embed", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("page_summary", sa.Text(), nullable=True),
        sa.Column("meta_created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta_updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["page_url"], ["scrapped_pages.page_url"], name=op.f("fk_chunk_summaries_page_url_scrapped_pages")
        ),
        sa.ForeignKeyConstraint(
            ["research_id"], ["researches.research_id"], name=op.f("fk_chunk_summaries_research_id_researches")
        ),
        sa.PrimaryKeyConstraint("chunk_id", name=op.f("pk_chunk_summaries")),
        sa.UniqueConstraint(
            "page_url", "research_id", "chunk_index", name=op.f("uq_chunk_summaries_page_url_research_id_chunk_index")
        ),
    )
    op.create_table(
        "model_outputs",
        sa.Column("response_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("model_id", sa.BigInteger(), nullable=False),
        sa.Column("research_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "response_status",
            postgresql.ENUM("PROCESSING", "COMPLETE", "ERROR", name="model_response_status_enum"),
            nullable=False,
        ),
        sa.Column("step_type", sa.Text(), nullable=False),
        sa.Column("model_input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_body", sa.Text(), nullable=True),
        sa.Column("meta_created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta_updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["models.model_id"], name=op.f("fk_model_outputs_model_id_models")),
        sa.ForeignKeyConstraint(
            ["research_id"], ["researches.research_id"], name=op.f("fk_model_outputs_research_id_researches")
        ),
        sa.PrimaryKeyConstraint("response_id", name=op.f("pk_model_outputs")),
    )
    op.create_table(
        "research_schedules",
        sa.Column("schedule_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("research_id", sa.BigInteger(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("repeat_interval", sa.Interval(), nullable=True),
        sa.Column("status", postgresql.ENUM("PLANNED", "COMPLETED", name="schedule_status_enum"), nullable=False),
        sa.Column("meta_created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("meta_updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_id"], ["researches.research_id"], name=op.f("fk_research_schedules_research_id_researches")
        ),
        sa.PrimaryKeyConstraint("schedule_id", name=op.f("pk_research_schedules")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("research_schedules")
    op.drop_table("model_outputs")
    op.drop_table("chunk_summaries")
    op.drop_table("user_notifications")
    op.drop_table("researches")
    op.drop_table("models")
    op.drop_table("users")
    op.drop_table("scrapped_pages")
