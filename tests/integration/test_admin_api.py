from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.api.routers.admin import router as admin_router
from app.core.config import Settings
from app.core.security import require_admin_api_token
from app.db.dependencies import get_db
from app.db.repositories.forms import FormRepository
from app.db.repositories.users import UserRepository
from app.main import app
from app.schemas.lead import LeadCreateInput
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from app.services.leads import LeadService
from httpx import ASGITransport, AsyncClient

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"
_BUNDLE = ContentService.load(_CONTENT_DIR)


@pytest.mark.asyncio
async def test_export_csv_route_is_not_shadowed_by_lead_detail_route(session) -> None:
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("consultation")
    user = await UserRepository(session).upsert_telegram_user(
        telegram_id=201,
        username="client",
        first_name="Client",
        last_name=None,
    )
    await LeadService(session, Settings(admin_ids=[999])).create_lead(
        LeadCreateInput(
            user_id=user.id,
            category_id=category.id,
            title=category.title,
            description="Need advice",
            contact_name="Client",
            contact_phone="@client",
            contact_username="client",
        )
    )

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_api_token] = lambda: None
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/leads/export.csv")
    finally:
        app.dependency_overrides.clear()

    route_paths = [route.path for route in admin_router.routes]
    assert route_paths.index("/admin/leads/export.csv") < route_paths.index(
        "/admin/leads/{lead_id}"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "TG-000001" in response.text


@pytest.mark.asyncio
async def test_admin_leads_route_filters_by_user_and_date(session) -> None:
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("consultation")
    user_repo = UserRepository(session)
    alpha = await user_repo.upsert_telegram_user(
        telegram_id=401,
        username="alpha",
        first_name="Alpha",
        last_name=None,
    )
    beta = await user_repo.upsert_telegram_user(
        telegram_id=402,
        username="beta",
        first_name="Beta",
        last_name=None,
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    await service.create_lead(
        LeadCreateInput(
            user_id=alpha.id,
            category_id=category.id,
            title=category.title,
            description="Alpha lead",
            contact_name="Alpha",
            contact_phone="@alpha",
            contact_username="alpha",
        )
    )
    await service.create_lead(
        LeadCreateInput(
            user_id=beta.id,
            category_id=category.id,
            title=category.title,
            description="Beta lead",
            contact_name="Beta",
            contact_phone="@beta",
            contact_username="beta",
        )
    )

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_api_token] = lambda: None
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            by_user = await client.get("/admin/leads", params={"user": "@alpha"})
            by_date = await client.get(
                "/admin/leads",
                params={"date_from": datetime.now(UTC).date().isoformat()},
            )
            by_future = await client.get(
                "/admin/leads",
                params={"date_from": (datetime.now(UTC) + timedelta(days=1)).date().isoformat()},
            )
    finally:
        app.dependency_overrides.clear()

    assert by_user.status_code == 200
    assert [item["contact_username"] for item in by_user.json()] == ["alpha"]
    assert len(by_date.json()) == 2
    assert by_future.json() == []
