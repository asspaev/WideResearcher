"""drop unique constraint on research_schedules.research_id

Revision ID: b0891120d7fc
Revises: 7ded7d66d292
Create Date: 2026-05-04 19:44:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "b0891120d7fc"
down_revision: Union[str, Sequence[str], None] = "7ded7d66d292"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("uq_research_schedules_research_id", "research_schedules", type_="unique")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_unique_constraint("uq_research_schedules_research_id", "research_schedules", ["research_id"])
