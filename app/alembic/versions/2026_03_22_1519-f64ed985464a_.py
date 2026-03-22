"""empty message

Revision ID: f64ed985464a
Revises: c5a7d2e8f301
Create Date: 2026-03-22 15:19:15.278222

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f64ed985464a"
down_revision: Union[str, Sequence[str], None] = "c5a7d2e8f301"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("models", "model_base_url", existing_type=sa.TEXT(), nullable=False)
    op.alter_column("models", "model_api_model", existing_type=sa.TEXT(), nullable=False)
    op.drop_column("models", "model_type")
    op.drop_column("models", "model_api_type")
    op.drop_column("models", "model_path")
    op.drop_column("models", "model_key_answer")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("models", sa.Column("model_key_answer", sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column("models", sa.Column("model_path", sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column("models", sa.Column("model_api_type", sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column("models", sa.Column("model_type", sa.TEXT(), autoincrement=False, nullable=False))
    op.alter_column("models", "model_api_model", existing_type=sa.TEXT(), nullable=True)
    op.alter_column("models", "model_base_url", existing_type=sa.TEXT(), nullable=True)
