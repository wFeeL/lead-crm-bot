from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import LeadStatus
from app.db.base import Base, CreatedAtMixin, TimestampMixin


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("user_id", "submission_key", name="uq_leads_user_id_submission_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    submission_key: Mapped[str | None] = mapped_column(String(64))
    category_id: Mapped[int] = mapped_column(
        ForeignKey("lead_categories.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=LeadStatus.NEW,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    contact_username: Mapped[str | None] = mapped_column(String(255))
    preferred_contact_time: Mapped[str | None] = mapped_column(String(255))
    assigned_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(64), default="telegram", nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", foreign_keys=[user_id], back_populates="leads")
    category = relationship("LeadCategory", back_populates="leads")
    assigned_admin = relationship(
        "User",
        foreign_keys=[assigned_admin_id],
        back_populates="assigned_leads",
    )
    answers = relationship("LeadAnswer", back_populates="lead", cascade="all, delete-orphan")
    files = relationship("LeadFile", back_populates="lead", cascade="all, delete-orphan")
    comments = relationship("LeadComment", back_populates="lead", cascade="all, delete-orphan")
    events = relationship("LeadEvent", back_populates="lead", cascade="all, delete-orphan")


class LeadAnswer(CreatedAtMixin, Base):
    __tablename__ = "lead_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("lead_questions.id"))
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_json: Mapped[dict | list | None] = mapped_column(JSON)
    lead = relationship("Lead", back_populates="answers")
    question = relationship("LeadQuestion", back_populates="answers")


class LeadFile(CreatedAtMixin, Base):
    __tablename__ = "lead_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    telegram_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    file_unique_id: Mapped[str | None] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    size: Mapped[int | None] = mapped_column(BigInteger)
    local_path: Mapped[str | None] = mapped_column(String(1024))
    lead = relationship("Lead", back_populates="files")


class LeadComment(CreatedAtMixin, Base):
    __tablename__ = "lead_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(default=True, nullable=False)
    lead = relationship("Lead", back_populates="comments")
    admin = relationship("User")


class LeadEvent(CreatedAtMixin, Base):
    __tablename__ = "lead_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict | list | None] = mapped_column(JSON)
    lead = relationship("Lead", back_populates="events")
    actor = relationship("User")
