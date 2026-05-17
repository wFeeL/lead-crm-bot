"""indexes and cascade rules

Revision ID: 0005_indexes_and_cascades
Revises: 0004_status_close_priority
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_indexes_and_cascades"
down_revision: str | Sequence[str] | None = "0004_status_close_priority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Indexes ---
    op.create_index(
        "ix_leads_assigned_admin_id", "leads", ["assigned_admin_id"], unique=False
    )
    op.create_index(
        "ix_leads_priority_created_at",
        "leads",
        ["priority", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_leads_status_created_at",
        "leads",
        ["status", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_lead_events_lead_created_at",
        "lead_events",
        ["lead_id", sa.text("created_at DESC")],
        unique=False,
    )

    # --- Cascade rules (batch for SQLite compat) ---

    # lead_comments.admin_id: make nullable + ON DELETE SET NULL
    with op.batch_alter_table("lead_comments", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_lead_comments_admin_id_users", type_="foreignkey")
        batch_op.alter_column("admin_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "fk_lead_comments_admin_id_users",
            "users",
            ["admin_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # leads.assigned_admin_id: ON DELETE SET NULL (already nullable)
    with op.batch_alter_table("leads", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_leads_assigned_admin_id_users", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_leads_assigned_admin_id_users",
            "users",
            ["assigned_admin_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    # Revert cascade rules
    with op.batch_alter_table("leads", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_leads_assigned_admin_id_users", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_leads_assigned_admin_id_users",
            "users",
            ["assigned_admin_id"],
            ["id"],
        )

    with op.batch_alter_table("lead_comments", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_lead_comments_admin_id_users", type_="foreignkey")
        batch_op.alter_column("admin_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_lead_comments_admin_id_users",
            "users",
            ["admin_id"],
            ["id"],
        )

    # Drop indexes
    op.drop_index("ix_lead_events_lead_created_at", table_name="lead_events")
    op.drop_index("ix_leads_status_created_at", table_name="leads")
    op.drop_index("ix_leads_priority_created_at", table_name="leads")
    op.drop_index("ix_leads_assigned_admin_id", table_name="leads")
