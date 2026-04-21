"""empty message

Revision ID: ac99a7cad22d
Revises: 9afdd17e4b8a
Create Date: 2026-04-21 08:23:42.861434

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ac99a7cad22d"
down_revision: Union[str, Sequence[str], None] = "9afdd17e4b8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("page_summaries", sa.Column("relevance_score", sa.Numeric(precision=4, scale=3), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("page_summaries", "relevance_score")
