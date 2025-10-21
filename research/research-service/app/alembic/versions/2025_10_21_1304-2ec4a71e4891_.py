"""empty message

Revision ID: 2ec4a71e4891
Revises:
Create Date: 2025-10-21 13:04:56.120392

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2ec4a71e4891"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "statuses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False, comment="Status name"),
        sa.Column("description", sa.Text(), nullable=False, comment="Status description"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_table(
        "researches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False, comment="Research name"),
        sa.Column("version", sa.Integer(), nullable=False, comment="Research version"),
        sa.Column("version_name", sa.Text(), nullable=False, comment="Version name"),
        sa.Column("input", sa.JSON(), nullable=False, comment="Input data"),
        sa.Column("answer", sa.JSON(), nullable=False, comment="Answer data"),
        sa.Column("status_id", sa.Integer(), nullable=False, comment="Research status"),
        sa.Column("date_start", sa.TIMESTAMP(), nullable=False, comment="Start date of research"),
        sa.Column("date_end", sa.TIMESTAMP(), nullable=False, comment="End date of research"),
        sa.Column("model_query_generator", sa.Integer(), nullable=False, comment="ID of query generator model"),
        sa.Column("model_extractor", sa.Integer(), nullable=False, comment="ID of extractor model"),
        sa.Column("model_ummarizer", sa.Integer(), nullable=False, comment="ID of summarizer model"),
        sa.ForeignKeyConstraint(
            ["status_id"],
            ["statuses.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("researches")
    op.drop_table("statuses")
