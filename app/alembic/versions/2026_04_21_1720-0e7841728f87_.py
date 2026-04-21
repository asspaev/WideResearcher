"""empty message

Revision ID: 0e7841728f87
Revises: a8b07e1cef14
Create Date: 2026-04-21 17:20:21.361266

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0e7841728f87"
down_revision: Union[str, Sequence[str], None] = "a8b07e1cef14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("researches", sa.Column("model_id_embed", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("researches", "model_id_embed")
