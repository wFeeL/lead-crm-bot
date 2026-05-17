"""add lead submission key

Revision ID: 0002_add_lead_submission_key
Revises: 0001_create_lead_tables
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_lead_submission_key"
down_revision: str | Sequence[str] | None = "0001_create_lead_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(sa.Column("submission_key", sa.String(length=64)))
        batch_op.create_unique_constraint(
            "uq_leads_user_id_submission_key",
            ["user_id", "submission_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_constraint("uq_leads_user_id_submission_key", type_="unique")
        batch_op.drop_column("submission_key")
