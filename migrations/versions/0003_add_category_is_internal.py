"""add is_internal flag to lead_categories

Revision ID: 0003_add_category_is_internal
Revises: 0002_add_lead_submission_key
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_category_is_internal"
down_revision: str | Sequence[str] | None = "0002_add_lead_submission_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lead_categories",
        sa.Column(
            "is_internal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("lead_categories", "is_internal")
