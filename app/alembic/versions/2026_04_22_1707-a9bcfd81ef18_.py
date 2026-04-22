"""empty message

Revision ID: a9bcfd81ef18
Revises: b7a51e6a8033
Create Date: 2026-04-22 17:07:21.427131

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9bcfd81ef18"
down_revision: Union[str, Sequence[str], None] = "b7a51e6a8033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("researches", sa.Column("settings_n_bm25_pages", sa.Integer(), server_default="10", nullable=False))
    op.add_column("researches", sa.Column("settings_n_embed_pages", sa.Integer(), server_default="10", nullable=False))
    op.add_column("researches", sa.Column("settings_n_rerank_pages", sa.Integer(), server_default="10", nullable=False))
    op.drop_column("researches", "settings_summarize_type")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "researches",
        sa.Column(
            "settings_summarize_type",
            sa.TEXT(),
            server_default=sa.text("'bm25'::text"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.drop_column("researches", "settings_n_rerank_pages")
    op.drop_column("researches", "settings_n_embed_pages")
    op.drop_column("researches", "settings_n_bm25_pages")
