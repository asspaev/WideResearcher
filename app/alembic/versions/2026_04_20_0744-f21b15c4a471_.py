"""empty message

Revision ID: f21b15c4a471
Revises: 0ff947975284
Create Date: 2026-04-20 07:44:56.520811

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f21b15c4a471"
down_revision: Union[str, Sequence[str], None] = "0ff947975284"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("models", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("researches", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("researches", "archived_at")
    op.drop_column("models", "archived_at")
