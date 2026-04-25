"""Change settings_search_areas and settings_exclude_search_areas from JSONB to TEXT

Revision ID: a1b2c3d4e5f6
Revises: 113ca3d13899
Create Date: 2026-04-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "113ca3d13899"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "researches",
        "settings_search_areas",
        type_=sa.Text(),
        postgresql_using="settings_search_areas::text",
        existing_nullable=True,
    )
    op.alter_column(
        "researches",
        "settings_exclude_search_areas",
        type_=sa.Text(),
        postgresql_using="settings_exclude_search_areas::text",
        existing_nullable=True,
    )
    op.alter_column(
        "researches",
        "settings_scenario_type",
        server_default="NORMAL",
        existing_type=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "researches",
        "settings_search_areas",
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="settings_search_areas::jsonb",
        existing_nullable=True,
    )
    op.alter_column(
        "researches",
        "settings_exclude_search_areas",
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="settings_exclude_search_areas::jsonb",
        existing_nullable=True,
    )
    op.alter_column(
        "researches",
        "settings_scenario_type",
        server_default="normal",
        existing_type=sa.Text(),
        existing_nullable=False,
    )
