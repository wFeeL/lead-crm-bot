from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import UserRole
from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.CLIENT, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    leads = relationship("Lead", foreign_keys="Lead.user_id", back_populates="user")
    assigned_leads = relationship(
        "Lead",
        foreign_keys="Lead.assigned_admin_id",
        back_populates="assigned_admin",
    )
