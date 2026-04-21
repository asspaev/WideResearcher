"""empty message

Revision ID: ad3df6025a77
Revises: ac99a7cad22d
Create Date: 2026-04-21 08:47:32.210902

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ad3df6025a77"
down_revision: Union[str, Sequence[str], None] = "ac99a7cad22d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("researches", sa.Column("research_error_body", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("researches", "research_error_body")
