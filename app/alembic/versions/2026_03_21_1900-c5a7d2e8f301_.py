"""add model_api_model to models

Revision ID: c5a7d2e8f301
Revises: b4661bdf477c
Create Date: 2026-03-21 19:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5a7d2e8f301"
down_revision: Union[str, Sequence[str], None] = "b4661bdf477c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("models", sa.Column("model_api_model", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("models", "model_api_model")
