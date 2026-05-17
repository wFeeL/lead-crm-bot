from pathlib import Path

import pytest
from app.db.repositories.forms import FormRepository
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from sqlalchemy.ext.asyncio import AsyncSession

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


@pytest.mark.asyncio
async def test_ensure_seed_data_from_default_profile(session: AsyncSession):
    bundle = ContentService.load(_CONTENT_DIR)
    await ensure_seed_data(session, bundle)
    await session.commit()

    repo = FormRepository(session)
    categories = await repo.list_categories()
    slugs = {c.slug for c in categories}
    assert slugs == {"telegram_bot", "website", "consultation", "other"}

    tg = await repo.get_category_by_slug("telegram_bot")
    assert tg is not None
    form = await repo.get_active_form(tg.id)
    assert form is not None
    # Form has 3 questions for telegram_bot per categories.yaml
    assert len(form.questions) == 3
    assert form.questions[0].key == "goal"


@pytest.mark.asyncio
async def test_ensure_seed_data_is_idempotent(session: AsyncSession):
    bundle = ContentService.load(_CONTENT_DIR)
    await ensure_seed_data(session, bundle)
    await session.commit()
    await ensure_seed_data(session, bundle)
    await session.commit()

    repo = FormRepository(session)
    categories = await repo.list_categories()
    # Still exactly 4 — no duplicates
    assert len(categories) == 4


def test_fastapi_lifespan_loads_content():
    from app.main import create_app
    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app):  # triggers lifespan startup
        assert app.state.content.brand.company_name == "LeadBot Demo"
