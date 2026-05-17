import csv
from datetime import UTC, date, datetime, timedelta
from io import StringIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import LeadStatus
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.security import is_admin
from app.db.models.lead import Lead
from app.db.models.user import User
from app.db.repositories.leads import LeadRepository
from app.schemas.lead import DailyStatsRead, LeadCreateInput
from app.services.status import assert_status_transition


class LeadService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = LeadRepository(session)

    async def create_lead(self, data: LeadCreateInput) -> Lead:
        if data.submission_key:
            existing = await self.repository.get_by_submission_key(
                user_id=data.user_id,
                submission_key=data.submission_key,
            )
            if existing is not None:
                existing.created_now = False
                return existing
        since = datetime.now(UTC) - timedelta(minutes=10)
        recent_count = await self.repository.count_recent_new_by_user(data.user_id, since=since)
        if recent_count >= self.settings.max_leads_per_10_minutes:
            raise ValidationError("too many leads created recently")
        if len(data.files) > self.settings.max_files_per_lead:
            raise ValidationError("too many files")
        for file in data.files:
            if file.size and file.size > self.settings.max_file_size_bytes:
                raise ValidationError("file is too large")
        return await self.repository.create(data)

    async def get_lead(self, lead_id: int) -> Lead:
        lead = await self.repository.get(lead_id)
        if lead is None:
            raise NotFoundError("lead not found")
        return lead

    async def list_leads(
        self,
        *,
        status: str | None = None,
        user_query: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        return await self.repository.list(
            status=status,
            user_query=user_query,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    async def list_user_leads(
        self,
        user_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        return await self.repository.list_by_user(user_id, limit=limit, offset=offset)

    async def change_status(
        self,
        *,
        lead_id: int,
        status: str,
        actor: User,
        reason: str | None = None,
    ) -> Lead:
        if not is_admin(actor.telegram_id, self.settings):
            raise PermissionDeniedError("admin privileges required")
        lead = await self.get_lead(lead_id)
        if lead.status == status:
            return lead
        assert_status_transition(lead.status, status)
        if reason is not None:
            lead.close_reason = reason
            self.session.add(lead)
            await self.session.flush()
        updated = await self.repository.update_status(
            lead=lead,
            status=status,
            actor_user_id=actor.id,
        )
        return updated

    async def build_draft_from_lead(self, *, lead_id: int, actor: User) -> dict:
        """Build a FSM-draft dict from an existing lead for the 'repeat' flow."""
        from uuid import uuid4

        lead = await self.get_lead(lead_id)
        if lead.user_id != actor.id:
            raise PermissionDeniedError("cannot repeat another user's lead")

        from app.db.repositories.forms import FormRepository

        form_repo = FormRepository(self.session)
        form = await form_repo.get_active_form(lead.category_id)
        if form is None or not form.questions:
            raise ValidationError("category form is unavailable")

        questions: list[dict] = []
        for q in form.questions:
            options = q.options_json if isinstance(q.options_json, list) else []
            questions.append(
                {
                    "id": q.id,
                    "key": q.key,
                    "text": q.question_text,
                    "type": q.question_type,
                    "required": q.is_required,
                    "options": [
                        str(o)
                        if not isinstance(o, dict)
                        else (o.get("label") or o.get("value") or "")
                        for o in options
                    ],
                }
            )

        question_by_id = {q["id"]: q for q in questions}
        answers: list[dict] = []
        for a in lead.answers:
            q = question_by_id.get(a.question_id)
            answers.append(
                {
                    "question_id": a.question_id,
                    "key": a.key,
                    "question_text": (q or {}).get("text", a.key),
                    "value_text": a.value_text or "",
                }
            )

        return {
            "submission_key": uuid4().hex,
            "category_id": lead.category_id,
            "category_title": lead.category.title if lead.category else "",
            "category_slug": lead.category.slug if lead.category else "",
            "questions": questions,
            "question_index": len(answers),
            "answers": answers,
            "files": [],
            "contact": lead.contact_phone
            or (f"@{lead.contact_username}" if lead.contact_username else None),
            "contact_phone": lead.contact_phone,
            "contact_username": lead.contact_username,
            "source": "repeat",
        }

    async def cancel_by_client(
        self,
        *,
        lead_id: int,
        actor: User,
        reason: str | None = None,
    ) -> Lead:
        """Cancel a lead by its owner."""
        lead = await self.get_lead(lead_id)
        if lead.user_id != actor.id:
            raise PermissionDeniedError("cannot cancel another user's lead")
        if lead.status == LeadStatus.CANCELLED:
            return lead
        if lead.status != LeadStatus.NEW:
            raise ValidationError("only new leads can be cancelled")
        if reason is not None:
            lead.close_reason = reason
            self.session.add(lead)
            await self.session.flush()
        return await self.repository.update_status(
            lead=lead,
            status=LeadStatus.CANCELLED,
            actor_user_id=actor.id,
        )

    async def assign_to_admin(self, *, lead_id: int, admin: User) -> Lead:
        if not is_admin(admin.telegram_id, self.settings):
            raise PermissionDeniedError("admin privileges required")
        lead = await self.get_lead(lead_id)
        if lead.assigned_admin_id == admin.id:
            return lead
        if lead.assigned_admin_id is not None:
            raise ValidationError("lead is already assigned to another admin")
        if lead.status in {LeadStatus.DONE, LeadStatus.REJECTED, LeadStatus.CANCELLED}:
            raise ValidationError("closed lead cannot be assigned")
        assigned = await self.repository.assign(lead=lead, admin_id=admin.id)
        if assigned.status == LeadStatus.NEW:
            return await self.repository.update_status(
                lead=assigned,
                status=LeadStatus.IN_PROGRESS,
                actor_user_id=admin.id,
            )
        return assigned

    async def set_priority(self, *, lead_id: int, priority: str, actor: User) -> Lead:
        from app.core.constants import LeadPriority

        if not is_admin(actor.telegram_id, self.settings):
            raise PermissionDeniedError("admin privileges required")
        try:
            LeadPriority(priority)
        except ValueError as exc:
            raise ValidationError("invalid priority") from exc
        lead = await self.get_lead(lead_id)
        if lead.priority == priority:
            return lead
        lead.priority = priority
        self.session.add(lead)
        await self.session.flush()
        return lead

    async def reassign(
        self,
        *,
        lead_id: int,
        new_admin: User | None,
        actor: User,
    ) -> Lead:
        if not is_admin(actor.telegram_id, self.settings):
            raise PermissionDeniedError("admin privileges required")
        lead = await self.get_lead(lead_id)
        prev_id = lead.assigned_admin_id
        new_id = new_admin.id if new_admin else None
        if prev_id == new_id:
            return lead
        if lead.status in {LeadStatus.DONE, LeadStatus.REJECTED, LeadStatus.CANCELLED}:
            raise ValidationError("closed lead cannot be reassigned")
        lead.assigned_admin_id = new_id
        self.session.add(lead)
        await self.session.flush()
        return lead

    async def add_comment(
        self,
        *,
        lead_id: int,
        admin: User,
        text: str,
        is_internal: bool = True,
    ) -> Lead:
        if not is_admin(admin.telegram_id, self.settings):
            raise PermissionDeniedError("admin privileges required")
        await self.get_lead(lead_id)
        await self.repository.add_comment(
            lead_id=lead_id,
            admin_id=admin.id,
            text=text,
            is_internal=is_internal,
        )
        return await self.get_lead(lead_id)

    async def export_csv(self) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "created_at",
                "status",
                "category",
                "name",
                "username",
                "phone",
                "description",
            ]
        )
        for row in await self.repository.export_rows():
            writer.writerow(row)
        return output.getvalue()

    async def daily_stats(self, day: date | None = None) -> DailyStatsRead:
        resolved_day = day or datetime.now(UTC).date()
        counts = await self.repository.daily_status_counts(resolved_day)
        top_category = await self.repository.top_category_for_day(resolved_day)
        return DailyStatsRead(
            date=resolved_day.isoformat(),
            new=counts.get(LeadStatus.NEW, 0),
            in_progress=counts.get(LeadStatus.IN_PROGRESS, 0),
            waiting=counts.get(LeadStatus.WAITING, 0),
            done=counts.get(LeadStatus.DONE, 0),
            rejected=counts.get(LeadStatus.REJECTED, 0),
            cancelled=counts.get(LeadStatus.CANCELLED, 0),
            top_category=top_category,
        )
