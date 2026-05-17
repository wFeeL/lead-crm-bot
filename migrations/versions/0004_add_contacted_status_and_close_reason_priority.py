"""add contacted status, close_reason, priority

Revision ID: 0004_add_contacted_status_and_close_reason_priority
Revises: 0003_add_category_is_internal
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_contacted_status_and_close_reason_priority"
down_revision: str | Sequence[str] | None = "0003_add_category_is_internal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("close_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column(
            "priority",
            sa.String(length=16),
            nullable=False,
            server_default="normal",
        ),
    )


def downgrade() -> None:
    op.drop_column("leads", "priority")
    op.drop_column("leads", "close_reason")
