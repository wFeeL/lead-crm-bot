from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.forms import FormRepository
from app.schemas.content import ContentBundle


async def ensure_seed_data(session: AsyncSession, content: ContentBundle) -> None:
    repository = FormRepository(session)
    for index, category_cfg in enumerate(content.categories):
        category = await repository.get_category_by_slug(category_cfg.slug)
        # Note: when category already exists (idempotent re-seed), is_internal is NOT
        # refreshed from YAML. Toggling internal in YAML requires a manual DB update.
        if category is None:
            category = await repository.create_category(
                slug=category_cfg.slug,
                title=category_cfg.title,
                description=category_cfg.description,
                sort_order=index,
                is_internal=category_cfg.internal,
            )
        form = await repository.get_active_form(category.id)
        if form is None:
            form = await repository.create_form(
                category_id=category.id,
                title=category_cfg.title,
                description=category_cfg.description,
            )
        questions_payload = [
            {
                "key": q.key,
                "text": q.text,
                "type": q.type,
                "required": q.required,
                "options": q.options,
            }
            for q in category_cfg.questions
        ]
        await repository.replace_questions(form, questions_payload)
