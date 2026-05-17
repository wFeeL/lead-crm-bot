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


def test_fastapi_lifespan_surfaces_content_error(tmp_path, monkeypatch):
    """If content profile is missing, the original FileNotFoundError must surface,
    not be masked by a secondary AttributeError in the finally block."""
    from app.main import create_app
    from fastapi.testclient import TestClient

    # Point CONTENT_PROFILE to a non-existent profile
    monkeypatch.setenv("CONTENT_PROFILE", "definitely-does-not-exist-12345")

    # Clear lru_cache on get_settings so the new env var is picked up
    from app.core.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    try:
        with pytest.raises(FileNotFoundError, match="brand.yaml"):
            with TestClient(app):
                pass
    finally:
        # Restore for other tests
        monkeypatch.delenv("CONTENT_PROFILE", raising=False)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ensure_seed_data_sets_is_internal_from_yaml(session: AsyncSession, tmp_path: Path):
    """seed honors CategoryConfig.internal flag."""
    import shutil

    profile = tmp_path / "internal_profile"
    profile.mkdir()
    # Copy default brand/texts/faq/config to satisfy ContentService.load();
    # override only categories.yaml
    for fname in ("brand.yaml", "texts.yaml", "faq.yaml", "config.yaml"):
        shutil.copy(_CONTENT_DIR / fname, profile / fname)
    (profile / "categories.yaml").write_text(
        "- slug: public_cat\n"
        "  title: Public\n"
        "  description: Visible to clients\n"
        "  questions:\n"
        "    - {key: q1, text: 'Q1', type: text, required: true}\n"
        "- slug: secret_cat\n"
        "  title: Secret\n"
        "  description: Hidden\n"
        "  internal: true\n"
        "  questions:\n"
        "    - {key: q1, text: 'Q1', type: text, required: true}\n",
        encoding="utf-8",
    )
    bundle = ContentService.load(profile)
    await ensure_seed_data(session, bundle)
    await session.commit()

    repo = FormRepository(session)
    public = await repo.get_category_by_slug("public_cat")
    secret = await repo.get_category_by_slug("secret_cat")
    assert public is not None and public.is_internal is False
    assert secret is not None and secret.is_internal is True

    # list_categories without include_internal hides secret_cat
    visible = await repo.list_categories()
    visible_slugs = {c.slug for c in visible}
    assert "public_cat" in visible_slugs
    assert "secret_cat" not in visible_slugs

    # list_categories with include_internal=True shows both
    all_cats = await repo.list_categories(include_internal=True)
    all_slugs = {c.slug for c in all_cats}
    assert "public_cat" in all_slugs
    assert "secret_cat" in all_slugs
