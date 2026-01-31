"""empty message

Revision ID: f82686fef541
Revises: 5b1d3ac96638
Create Date: 2026-01-30 17:16:04.724409

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f82686fef541"
down_revision: Union[str, Sequence[str], None] = "5b1d3ac96638"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("models", sa.Column("model_api_type", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("models", "model_api_type")
