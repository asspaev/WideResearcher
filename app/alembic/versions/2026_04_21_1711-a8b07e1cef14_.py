"""empty message

Revision ID: a8b07e1cef14
Revises: ad3df6025a77
Create Date: 2026-04-21 17:11:01.580843

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8b07e1cef14"
down_revision: Union[str, Sequence[str], None] = "ad3df6025a77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("models", sa.Column("model_type", sa.String(length=50), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("models", "model_type")
