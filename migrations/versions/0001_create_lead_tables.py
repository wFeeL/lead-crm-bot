"""create lead tables

Revision ID: 0001_create_lead_tables
Revises:
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_lead_tables"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        now_column("created_at"),
        now_column("updated_at"),
    ]


def now_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255)),
        sa.Column("first_name", sa.String(length=255)),
        sa.Column("last_name", sa.String(length=255)),
        sa.Column("phone", sa.String(length=64)),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), nullable=False),
        now_column("last_seen_at"),
        *timestamp_columns(),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "lead_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        now_column("created_at"),
    )
    op.create_index("ix_lead_categories_slug", "lead_categories", ["slug"], unique=True)

    op.create_table(
        "lead_forms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("lead_categories.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamp_columns(),
    )

    op.create_table(
        "lead_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("form_id", sa.Integer(), sa.ForeignKey("lead_forms.id"), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=32), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("options_json", sa.JSON()),
        sa.Column("validation_json", sa.JSON()),
        now_column("created_at"),
    )

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(length=32)),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("lead_categories.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.String(length=255)),
        sa.Column("contact_phone", sa.String(length=64)),
        sa.Column("contact_username", sa.String(length=255)),
        sa.Column("preferred_contact_time", sa.String(length=255)),
        sa.Column("assigned_admin_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        *timestamp_columns(),
    )
    op.create_index("ix_leads_public_id", "leads", ["public_id"], unique=True)
    op.create_index("ix_leads_user_id", "leads", ["user_id"])
    op.create_index("ix_leads_category_id", "leads", ["category_id"])
    op.create_index("ix_leads_status", "leads", ["status"])

    op.create_table(
        "lead_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("lead_questions.id")),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value_text", sa.Text()),
        sa.Column("value_json", sa.JSON()),
        now_column("created_at"),
    )
    op.create_index("ix_lead_answers_lead_id", "lead_answers", ["lead_id"])

    op.create_table(
        "lead_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=False),
        sa.Column("file_unique_id", sa.String(length=255)),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("file_name", sa.String(length=255)),
        sa.Column("mime_type", sa.String(length=255)),
        sa.Column("size", sa.BigInteger()),
        sa.Column("local_path", sa.String(length=1024)),
        now_column("created_at"),
    )
    op.create_index("ix_lead_files_lead_id", "lead_files", ["lead_id"])

    op.create_table(
        "lead_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False),
        now_column("created_at"),
    )
    op.create_index("ix_lead_comments_lead_id", "lead_comments", ["lead_id"])

    op.create_table(
        "lead_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("old_value", sa.Text()),
        sa.Column("new_value", sa.Text()),
        sa.Column("payload_json", sa.JSON()),
        now_column("created_at"),
    )
    op.create_index("ix_lead_events_lead_id", "lead_events", ["lead_id"])

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value_json", sa.JSON()),
        now_column("updated_at"),
    )
    op.create_index("ix_settings_key", "settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_table("lead_events")
    op.drop_table("lead_comments")
    op.drop_table("lead_files")
    op.drop_table("lead_answers")
    op.drop_table("leads")
    op.drop_table("lead_questions")
    op.drop_table("lead_forms")
    op.drop_table("lead_categories")
    op.drop_table("users")
