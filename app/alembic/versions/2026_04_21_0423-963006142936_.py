"""empty message

Revision ID: 963006142936
Revises: 1148f1c1dd5d
Create Date: 2026-04-21 04:23:29.607877

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "963006142936"
down_revision: Union[str, Sequence[str], None] = "1148f1c1dd5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("model_outputs", sa.Column("error_body", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("model_outputs", "error_body")
