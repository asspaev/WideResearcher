"""add model_n_async column to models

Revision ID: c1f4a2b3d5e7
Revises: b0891120d7fc
Create Date: 2026-05-16 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1f4a2b3d5e7"
down_revision: Union[str, Sequence[str], None] = "b0891120d7fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "models",
        sa.Column("model_n_async", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("models", "model_n_async")
