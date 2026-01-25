"""empty message

Revision ID: 0de78b1de3e3
Revises: ec0bb66cf4dd
Create Date: 2026-01-25 11:51:51.035992

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0de78b1de3e3"
down_revision: Union[str, Sequence[str], None] = "ec0bb66cf4dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "user_password_hash",
        existing_type=sa.TEXT(),
        type_=sa.LargeBinary(),
        existing_nullable=False,
        postgresql_using="user_password_hash::bytea",
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "user_password_hash",
        existing_type=sa.LargeBinary(),
        type_=sa.TEXT(),
        existing_nullable=False,
        postgresql_using="encode(user_password_hash, 'escape')",
    )
