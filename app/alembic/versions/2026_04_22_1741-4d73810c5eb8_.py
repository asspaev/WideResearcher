"""empty message

Revision ID: 4d73810c5eb8
Revises: a9bcfd81ef18
Create Date: 2026-04-22 17:41:14.010672

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4d73810c5eb8"
down_revision: Union[str, Sequence[str], None] = "a9bcfd81ef18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("page_summaries", sa.Column("page_embed", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "researches", sa.Column("research_result_embed_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("researches", "research_result_embed_summary")
    op.drop_column("page_summaries", "page_embed")
