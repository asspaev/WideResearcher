"""empty message

Revision ID: e5fa437aca6d
Revises: f21b15c4a471
Create Date: 2026-04-20 12:22:08.846570

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5fa437aca6d"
down_revision: Union[str, Sequence[str], None] = "f21b15c4a471"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("research_epoches", sa.Column("epoch_duration_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("research_epoches", "epoch_duration_seconds")
