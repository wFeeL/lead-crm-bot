from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.category import LeadCategory, LeadForm, LeadQuestion


class FormRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_categories(self, *, active_only: bool = True) -> list[LeadCategory]:
        stmt = select(LeadCategory).order_by(LeadCategory.sort_order, LeadCategory.id)
        if active_only:
            stmt = stmt.where(LeadCategory.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_category_by_slug(self, slug: str) -> LeadCategory | None:
        result = await self.session.execute(select(LeadCategory).where(LeadCategory.slug == slug))
        return result.scalar_one_or_none()

    async def get_category(self, category_id: int) -> LeadCategory | None:
        return await self.session.get(LeadCategory, category_id)

    async def get_active_form(self, category_id: int) -> LeadForm | None:
        result = await self.session.execute(
            select(LeadForm)
            .options(selectinload(LeadForm.questions))
            .where(LeadForm.category_id == category_id, LeadForm.is_active.is_(True))
            .order_by(LeadForm.id)
        )
        return result.scalars().first()

    async def create_category(
        self,
        *,
        slug: str,
        title: str,
        description: str | None,
        sort_order: int,
    ) -> LeadCategory:
        category = LeadCategory(
            slug=slug,
            title=title,
            description=description,
            sort_order=sort_order,
            is_active=True,
        )
        self.session.add(category)
        await self.session.flush()
        return category

    async def create_form(
        self,
        *,
        category_id: int,
        title: str,
        description: str | None,
    ) -> LeadForm:
        form = LeadForm(
            category_id=category_id,
            title=title,
            description=description,
            is_active=True,
        )
        self.session.add(form)
        await self.session.flush()
        return form

    async def replace_questions(self, form: LeadForm, questions: list[dict]) -> None:
        existing = await self.session.execute(
            select(LeadQuestion).where(LeadQuestion.form_id == form.id)
        )
        for question in existing.scalars().all():
            await self.session.delete(question)
        await self.session.flush()
        for index, question in enumerate(questions):
            self.session.add(
                LeadQuestion(
                    form_id=form.id,
                    key=question["key"],
                    question_text=question["text"],
                    question_type=question["type"],
                    is_required=question.get("required", True),
                    sort_order=index,
                    options_json=question.get("options"),
                    validation_json=question.get("validation"),
                )
            )
        await self.session.flush()

