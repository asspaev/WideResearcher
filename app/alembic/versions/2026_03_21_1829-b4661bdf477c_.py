"""add model_base_url to models

Revision ID: b4661bdf477c
Revises: f82686fef541
Create Date: 2026-03-21 18:29:25.634262

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4661bdf477c"
down_revision: Union[str, Sequence[str], None] = "f82686fef541"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("models", sa.Column("model_base_url", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("models", "model_base_url")
