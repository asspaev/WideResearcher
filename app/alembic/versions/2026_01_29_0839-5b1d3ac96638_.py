"""empty message

Revision ID: 5b1d3ac96638
Revises: 0de78b1de3e3
Create Date: 2026-01-29 08:39:57.019301

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b1d3ac96638"
down_revision: Union[str, Sequence[str], None] = "0de78b1de3e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "researches", sa.Column("research_version_name", sa.Text(), nullable=False, server_default="Без названия")
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("researches", "research_version_name")
