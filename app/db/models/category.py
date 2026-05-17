from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin


class LeadCategory(CreatedAtMixin, Base):
    __tablename__ = "lead_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_internal: Mapped[bool] = mapped_column(default=False, nullable=False)
    forms = relationship("LeadForm", back_populates="category", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="category")


class LeadForm(TimestampMixin, Base):
    __tablename__ = "lead_forms"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("lead_categories.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    category = relationship("LeadCategory", back_populates="forms")
    questions = relationship(
        "LeadQuestion",
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="LeadQuestion.sort_order",
    )


class LeadQuestion(CreatedAtMixin, Base):
    __tablename__ = "lead_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("lead_forms.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_required: Mapped[bool] = mapped_column(default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    options_json: Mapped[dict | list | None] = mapped_column(JSON)
    validation_json: Mapped[dict | None] = mapped_column(JSON)
    form = relationship("LeadForm", back_populates="questions")
    answers = relationship("LeadAnswer", back_populates="question")
