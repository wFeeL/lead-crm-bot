from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import QuestionType
from app.db.repositories.forms import FormRepository
from app.schemas.content import ContentBundle

LEAD_FORM_DEFINITIONS: list[dict] = [
    {
        "slug": "telegram_bot",
        "title": "Разработка бота",
        "description": "Telegram-боты и автоматизация",
        "questions": [
            {
                "key": "goal",
                "text": "Что должен делать бот?",
                "type": QuestionType.LONG_TEXT,
                "required": True,
            },
            {
                "key": "deadline",
                "text": "Какие сроки?",
                "type": QuestionType.TEXT,
                "required": False,
            },
            {
                "key": "budget",
                "text": "Какой ориентировочный бюджет?",
                "type": QuestionType.TEXT,
                "required": False,
            },
        ],
    },
    {
        "slug": "website",
        "title": "Сайт / backend",
        "description": "Сайты, API и backend-разработка",
        "questions": [
            {
                "key": "project_type",
                "text": "Какой проект нужен?",
                "type": QuestionType.TEXT,
                "required": True,
            },
            {
                "key": "features",
                "text": "Какие основные функции нужны?",
                "type": QuestionType.LONG_TEXT,
                "required": True,
            },
            {
                "key": "deadline",
                "text": "Есть ли дедлайн?",
                "type": QuestionType.TEXT,
                "required": False,
            },
        ],
    },
    {
        "slug": "consultation",
        "title": "Консультация",
        "description": "Разбор задачи и техническая консультация",
        "questions": [
            {
                "key": "topic",
                "text": "По какой теме нужна консультация?",
                "type": QuestionType.TEXT,
                "required": True,
            },
            {
                "key": "context",
                "text": "Опишите контекст задачи.",
                "type": QuestionType.LONG_TEXT,
                "required": False,
            },
        ],
    },
    {
        "slug": "other",
        "title": "Другое",
        "description": "Любая другая заявка",
        "questions": [
            {
                "key": "description",
                "text": "Опишите задачу.",
                "type": QuestionType.LONG_TEXT,
                "required": True,
            }
        ],
    },
]


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
