"""empty message

Revision ID: 7ded7d66d292
Revises: 6e3860a892bd
Create Date: 2026-05-04 05:24:38.334813

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7ded7d66d292"
down_revision: Union[str, Sequence[str], None] = "6e3860a892bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("research_schedules", sa.Column("research_parent_id", sa.BigInteger(), nullable=True))
    op.add_column("research_schedules", sa.Column("settings_search_areas", sa.Text(), nullable=True))
    op.add_column("research_schedules", sa.Column("settings_exclude_search_areas", sa.Text(), nullable=True))
    op.add_column(
        "research_schedules", sa.Column("settings_n_async_parse", sa.Integer(), server_default="3", nullable=False)
    )
    op.add_column(
        "research_schedules", sa.Column("settings_scenario_type", sa.Text(), server_default="NORMAL", nullable=False)
    )
    op.add_column(
        "research_schedules", sa.Column("settings_n_vectors", sa.Integer(), server_default="5", nullable=False)
    )
    op.add_column(
        "research_schedules", sa.Column("settings_n_search_queries", sa.Integer(), server_default="5", nullable=False)
    )
    op.add_column(
        "research_schedules",
        sa.Column("settings_n_top_search_results", sa.Integer(), server_default="10", nullable=False),
    )
    op.add_column(
        "research_schedules", sa.Column("settings_n_top_bm25_chunks", sa.Integer(), server_default="50", nullable=False)
    )
    op.add_column(
        "research_schedules",
        sa.Column("settings_n_top_embed_chunks", sa.Integer(), server_default="30", nullable=False),
    )
    op.add_column(
        "research_schedules",
        sa.Column("settings_n_top_rerank_chunks", sa.Integer(), server_default="15", nullable=False),
    )
    op.add_column(
        "research_schedules", sa.Column("settings_n_top_chunks", sa.Integer(), server_default="15", nullable=False)
    )
    op.add_column(
        "research_schedules", sa.Column("model_id_answer", sa.BigInteger(), server_default="0", nullable=False)
    )
    op.alter_column("research_schedules", "model_id_answer", server_default=None)
    op.add_column(
        "research_schedules", sa.Column("model_id_search", sa.BigInteger(), server_default="0", nullable=False)
    )
    op.alter_column("research_schedules", "model_id_search", server_default=None)
    op.add_column("research_schedules", sa.Column("model_id_direction", sa.BigInteger(), nullable=True))
    op.add_column("research_schedules", sa.Column("model_id_embed", sa.BigInteger(), nullable=True))
    op.add_column("research_schedules", sa.Column("model_id_reranker", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_research_schedules_research_parent_id_researches"),
        "research_schedules",
        "researches",
        ["research_parent_id"],
        ["research_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_research_schedules_research_parent_id_researches"), "research_schedules", type_="foreignkey"
    )
    op.drop_column("research_schedules", "model_id_reranker")
    op.drop_column("research_schedules", "model_id_embed")
    op.drop_column("research_schedules", "model_id_direction")
    op.drop_column("research_schedules", "model_id_search")
    op.drop_column("research_schedules", "model_id_answer")
    op.drop_column("research_schedules", "settings_n_top_chunks")
    op.drop_column("research_schedules", "settings_n_top_rerank_chunks")
    op.drop_column("research_schedules", "settings_n_top_embed_chunks")
    op.drop_column("research_schedules", "settings_n_top_bm25_chunks")
    op.drop_column("research_schedules", "settings_n_top_search_results")
    op.drop_column("research_schedules", "settings_n_search_queries")
    op.drop_column("research_schedules", "settings_n_vectors")
    op.drop_column("research_schedules", "settings_scenario_type")
    op.drop_column("research_schedules", "settings_n_async_parse")
    op.drop_column("research_schedules", "settings_exclude_search_areas")
    op.drop_column("research_schedules", "settings_search_areas")
    op.drop_column("research_schedules", "research_parent_id")
