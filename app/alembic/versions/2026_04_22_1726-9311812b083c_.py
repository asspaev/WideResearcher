"""empty message

Revision ID: 9311812b083c
Revises: a9bcfd81ef18
Create Date: 2026-04-22 17:26:17.700452

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9311812b083c"
down_revision: Union[str, Sequence[str], None] = "a9bcfd81ef18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("page_summaries", sa.Column("page_embed", sa.Float(precision=53), nullable=True))
    op.add_column("researches", sa.Column("research_result_embed_summary", sa.Float(precision=53), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("researches", "research_result_embed_summary")
    op.drop_column("page_summaries", "page_embed")
