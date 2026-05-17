from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import HIDDEN_STATUSES, LeadEventType, LeadStatus
from app.db.models.category import LeadCategory
from app.db.models.lead import Lead, LeadAnswer, LeadComment, LeadEvent, LeadFile
from app.db.models.user import User
from app.schemas.lead import LeadCreateInput


class LeadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _hidden_status_values() -> tuple[str, ...]:
        """Statuses that should never appear in any list query (soft-deleted)."""
        return tuple(str(s) for s in HIDDEN_STATUSES)

    def _lead_options(self) -> tuple:
        return (
            selectinload(Lead.answers).selectinload(LeadAnswer.question),
            selectinload(Lead.files),
            selectinload(Lead.comments).selectinload(LeadComment.admin),
            selectinload(Lead.category),
            selectinload(Lead.user),
            selectinload(Lead.assigned_admin),
        )

    async def get(self, lead_id: int) -> Lead | None:
        result = await self.session.execute(
            select(Lead)
            .options(*self._lead_options())
            .where(Lead.id == lead_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_submission_key(self, *, user_id: int, submission_key: str) -> Lead | None:
        result = await self.session.execute(
            select(Lead)
            .options(*self._lead_options())
            .where(Lead.user_id == user_id, Lead.submission_key == submission_key)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        status: str | None = None,
        user_query: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        stmt: Select = (
            select(Lead)
            .options(*self._lead_options())
            .where(Lead.status.not_in(self._hidden_status_values()))
            .order_by(Lead.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(Lead.status == status)
        if user_query:
            normalized_query = user_query.strip().removeprefix("@")
            stmt = stmt.join(User, Lead.user_id == User.id)
            if normalized_query.isdigit():
                stmt = stmt.where(
                    (User.telegram_id == int(normalized_query))
                    | (Lead.public_id == normalized_query)
                )
            else:
                stmt = stmt.where(User.username.ilike(f"%{normalized_query}%"))
        if date_from:
            start = datetime.combine(date_from, time.min, tzinfo=UTC)
            stmt = stmt.where(Lead.created_at >= start)
        if date_to:
            end = datetime.combine(date_to, time.max, tzinfo=UTC)
            stmt = stmt.where(Lead.created_at <= end)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_user(
        self,
        user_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        result = await self.session.execute(
            select(Lead)
            .options(*self._lead_options())
            .where(
                Lead.user_id == user_id,
                Lead.status.not_in(self._hidden_status_values()),
            )
            .order_by(Lead.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: int) -> int:
        from sqlalchemy import func, select

        result = await self.session.execute(
            select(func.count())
            .select_from(Lead)
            .where(
                Lead.user_id == user_id,
                Lead.status.not_in(self._hidden_status_values()),
            )
        )
        return int(result.scalar_one())

    async def count_recent_new_by_user(self, user_id: int, *, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count(Lead.id)).where(
                Lead.user_id == user_id,
                Lead.created_at >= since,
            )
        )
        return int(result.scalar_one())

    async def create(self, data: LeadCreateInput) -> Lead:
        if data.submission_key:
            existing = await self.get_by_submission_key(
                user_id=data.user_id,
                submission_key=data.submission_key,
            )
            if existing is not None:
                existing.created_now = False
                return existing
        try:
            async with self.session.begin_nested():
                lead = Lead(
                    user_id=data.user_id,
                    submission_key=data.submission_key,
                    category_id=data.category_id,
                    status=LeadStatus.NEW,
                    title=data.title,
                    description=data.description,
                    contact_name=data.contact_name,
                    contact_phone=data.contact_phone,
                    contact_username=data.contact_username,
                    preferred_contact_time=data.preferred_contact_time,
                    source=data.source,
                )
                self.session.add(lead)
                await self.session.flush()
                lead.public_id = f"TG-{lead.id:06d}"
                for answer in data.answers:
                    self.session.add(
                        LeadAnswer(
                            lead_id=lead.id,
                            question_id=answer.question_id,
                            key=answer.key,
                            value_text=answer.value_text,
                            value_json=answer.value_json,
                        )
                    )
                for file in data.files:
                    self.session.add(
                        LeadFile(
                            lead_id=lead.id,
                            telegram_file_id=file.telegram_file_id,
                            file_unique_id=file.file_unique_id,
                            file_type=file.file_type,
                            file_name=file.file_name,
                            mime_type=file.mime_type,
                            size=file.size,
                        )
                    )
                self.session.add(
                    LeadEvent(
                        lead_id=lead.id,
                        actor_user_id=data.user_id,
                        event_type=LeadEventType.LEAD_CREATED,
                        new_value=LeadStatus.NEW,
                    )
                )
                await self.session.flush()
        except IntegrityError:
            if data.submission_key:
                existing = await self.get_by_submission_key(
                    user_id=data.user_id,
                    submission_key=data.submission_key,
                )
                if existing is not None:
                    existing.created_now = False
                    return existing
            raise
        refreshed = await self.get(lead.id)
        if refreshed is None:
            raise RuntimeError("lead was not created")
        refreshed.created_now = True
        return refreshed

    async def update_status(
        self,
        *,
        lead: Lead,
        status: str,
        actor_user_id: int | None,
    ) -> Lead:
        old_status = lead.status
        lead.status = status
        if status in {LeadStatus.DONE, LeadStatus.REJECTED, LeadStatus.CANCELLED}:
            lead.closed_at = datetime.now(UTC)
        self.session.add(
            LeadEvent(
                lead_id=lead.id,
                actor_user_id=actor_user_id,
                event_type=LeadEventType.STATUS_CHANGED,
                old_value=old_status,
                new_value=status,
            )
        )
        await self.session.flush()
        refreshed = await self.get(lead.id)
        if refreshed is None:
            raise RuntimeError("lead disappeared after status update")
        return refreshed

    async def assign(self, *, lead: Lead, admin_id: int) -> Lead:
        lead.assigned_admin_id = admin_id
        self.session.add(
            LeadEvent(
                lead_id=lead.id,
                actor_user_id=admin_id,
                event_type=LeadEventType.ADMIN_ASSIGNED,
                new_value=str(admin_id),
            )
        )
        await self.session.flush()
        refreshed = await self.get(lead.id)
        if refreshed is None:
            raise RuntimeError("lead disappeared after assignment")
        return refreshed

    async def soft_delete(
        self,
        *,
        lead: Lead,
        actor_user_id: int | None,
    ) -> Lead:
        """Mark a lead as deleted. Rows remain for history; queries filter it out."""
        old_status = lead.status
        lead.status = LeadStatus.DELETED
        lead.closed_at = datetime.now(UTC)
        self.session.add(
            LeadEvent(
                lead_id=lead.id,
                actor_user_id=actor_user_id,
                event_type=LeadEventType.LEAD_DELETED,
                old_value=old_status,
                new_value=LeadStatus.DELETED,
            )
        )
        await self.session.flush()
        return lead

    async def add_comment(
        self,
        *,
        lead_id: int,
        admin_id: int,
        text: str,
        is_internal: bool = True,
    ) -> LeadComment:
        comment = LeadComment(
            lead_id=lead_id,
            admin_id=admin_id,
            text=text,
            is_internal=is_internal,
        )
        self.session.add(comment)
        self.session.add(
            LeadEvent(
                lead_id=lead_id,
                actor_user_id=admin_id,
                event_type=LeadEventType.COMMENT_ADDED,
                new_value=text[:500],
            )
        )
        await self.session.flush()
        return comment

    async def daily_status_counts(self, day: date) -> dict[str, int]:
        start = datetime.combine(day, time.min, tzinfo=UTC)
        end = datetime.combine(day, time.max, tzinfo=UTC)
        result = await self.session.execute(
            select(Lead.status, func.count(Lead.id))
            .where(Lead.created_at >= start, Lead.created_at <= end)
            .group_by(Lead.status)
        )
        return {status: int(count) for status, count in result.all()}

    async def top_category_for_day(self, day: date) -> str | None:
        start = datetime.combine(day, time.min, tzinfo=UTC)
        end = datetime.combine(day, time.max, tzinfo=UTC)
        result = await self.session.execute(
            select(LeadCategory.title, func.count(Lead.id).label("lead_count"))
            .join(Lead, Lead.category_id == LeadCategory.id)
            .where(Lead.created_at >= start, Lead.created_at <= end)
            .group_by(LeadCategory.title)
            .order_by(func.count(Lead.id).desc())
            .limit(1)
        )
        row = result.first()
        return row[0] if row else None

    async def status_counts(self) -> dict[str, int]:
        """Total count per status across all non-hidden leads."""
        from sqlalchemy import func, select

        result = await self.session.execute(
            select(Lead.status, func.count(Lead.id))
            .where(Lead.status.not_in(self._hidden_status_values()))
            .group_by(Lead.status)
        )
        return {row[0]: row[1] for row in result.all()}

    async def hot_count(self) -> int:
        """Count of non-terminal, non-deleted leads with priority high or urgent."""
        from sqlalchemy import func, select

        result = await self.session.execute(
            select(func.count(Lead.id)).where(
                Lead.priority.in_(("high", "urgent")),
                Lead.status.not_in(("done", "rejected", "cancelled")),
                Lead.status.not_in(self._hidden_status_values()),
            )
        )
        return int(result.scalar_one())

    async def list_by_filter(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        hot: bool = False,
        limit: int = 5,
        offset: int = 0,
    ) -> list[Lead]:
        """List leads sorted by priority DESC then created_at DESC."""
        from sqlalchemy import case, desc, select

        # priority sort: urgent > high > normal > low. Map to numeric.
        priority_order = case(
            (Lead.priority == "urgent", 4),
            (Lead.priority == "high", 3),
            (Lead.priority == "normal", 2),
            (Lead.priority == "low", 1),
            else_=0,
        )
        stmt = (
            select(Lead)
            .options(*self._lead_options())
            .where(Lead.status.not_in(self._hidden_status_values()))
        )
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if priority is not None:
            stmt = stmt.where(Lead.priority == priority)
        if hot:
            stmt = stmt.where(
                Lead.priority.in_(("high", "urgent")),
                Lead.status.not_in(("done", "rejected", "cancelled")),
            )
        stmt = (
            stmt.order_by(desc(priority_order), desc(Lead.created_at)).limit(limit).offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_filter(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        hot: bool = False,
    ) -> int:
        from sqlalchemy import func, select

        stmt = select(func.count(Lead.id)).where(Lead.status.not_in(self._hidden_status_values()))
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if priority is not None:
            stmt = stmt.where(Lead.priority == priority)
        if hot:
            stmt = stmt.where(
                Lead.priority.in_(("high", "urgent")),
                Lead.status.not_in(("done", "rejected", "cancelled")),
            )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def export_rows(self) -> list[tuple]:
        result = await self.session.execute(
            select(
                Lead.public_id,
                Lead.created_at,
                Lead.status,
                LeadCategory.title,
                Lead.contact_name,
                User.username,
                Lead.contact_phone,
                Lead.description,
            )
            .join(LeadCategory, Lead.category_id == LeadCategory.id)
            .join(User, Lead.user_id == User.id)
            .order_by(Lead.created_at.desc())
        )
        return list(result.all())
