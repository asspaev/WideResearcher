"""empty message

Revision ID: 9afdd17e4b8a
Revises: 963006142936
Create Date: 2026-04-21 05:11:01.654163

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9afdd17e4b8a"
down_revision: Union[str, Sequence[str], None] = "963006142936"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("researches", sa.Column("settings_n_vectors", sa.Integer(), server_default="5", nullable=False))
    op.add_column(
        "researches", sa.Column("settings_n_search_queries", sa.Integer(), server_default="5", nullable=False)
    )
    op.add_column("researches", sa.Column("settings_n_top_pages", sa.Integer(), server_default="10", nullable=False))
    op.add_column("researches", sa.Column("settings_n_async_parse", sa.Integer(), server_default="3", nullable=False))
    op.add_column("researches", sa.Column("settings_summarize_type", sa.Text(), server_default="bm25", nullable=False))
    op.add_column("researches", sa.Column("settings_scenario_type", sa.Text(), server_default="normal", nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("researches", "settings_scenario_type")
    op.drop_column("researches", "settings_summarize_type")
    op.drop_column("researches", "settings_n_async_parse")
    op.drop_column("researches", "settings_n_top_pages")
    op.drop_column("researches", "settings_n_search_queries")
    op.drop_column("researches", "settings_n_vectors")
