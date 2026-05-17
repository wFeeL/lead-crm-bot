from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.constants import LeadStatus
from app.db.repositories.forms import FormRepository
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.schemas.lead import LeadAnswerInput, LeadCreateInput
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from app.services.leads import LeadService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"
_BUNDLE = ContentService.load(_CONTENT_DIR)


@pytest.mark.asyncio
async def test_seed_and_create_lead(session) -> None:
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("telegram_bot")
    form = await FormRepository(session).get_active_form(category.id)
    user = await UserRepository(session).upsert_telegram_user(
        telegram_id=100,
        username="client",
        first_name="Client",
        last_name=None,
    )
    service = LeadService(session, Settings(admin_ids=[999]))

    lead = await service.create_lead(
        LeadCreateInput(
            user_id=user.id,
            category_id=category.id,
            title=category.title,
            description="Need a lead bot",
            contact_name="Client",
            contact_phone="+79990000000",
            contact_username="client",
            answers=[
                LeadAnswerInput(
                    question_id=form.questions[0].id,
                    key=form.questions[0].key,
                    value_text="Need a lead bot",
                )
            ],
        )
    )

    assert lead.public_id == "TG-000001"
    assert lead.status == LeadStatus.NEW
    assert lead.answers[0].key == "goal"


@pytest.mark.asyncio
async def test_create_lead_is_idempotent_by_submission_key(session) -> None:
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("telegram_bot")
    user = await UserRepository(session).upsert_telegram_user(
        telegram_id=103,
        username="client",
        first_name="Client",
        last_name=None,
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    payload = LeadCreateInput(
        user_id=user.id,
        category_id=category.id,
        submission_key="draft-103",
        title=category.title,
        description="Need a lead bot",
        contact_name="Client",
        contact_phone="+79990000000",
        contact_username="client",
    )

    first = await service.create_lead(payload)
    second = await service.create_lead(payload)
    leads = await service.list_user_leads(user.id)

    assert second.id == first.id
    assert [lead.id for lead in leads] == [first.id]


@pytest.mark.asyncio
async def test_client_can_cancel_new_lead(session) -> None:
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("other")
    user = await UserRepository(session).upsert_telegram_user(
        telegram_id=101,
        username="client",
        first_name="Client",
        last_name=None,
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    lead = await service.create_lead(
        LeadCreateInput(
            user_id=user.id,
            category_id=category.id,
            title=category.title,
            description="Other task",
            contact_name="Client",
            contact_phone="@client",
            contact_username="client",
        )
    )

    cancelled = await service.cancel_by_client(lead_id=lead.id, actor=user)

    assert cancelled.status == LeadStatus.CANCELLED


@pytest.mark.asyncio
async def test_client_cancel_is_safe_to_repeat(session) -> None:
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("other")
    user = await UserRepository(session).upsert_telegram_user(
        telegram_id=104,
        username="client",
        first_name="Client",
        last_name=None,
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    lead = await service.create_lead(
        LeadCreateInput(
            user_id=user.id,
            category_id=category.id,
            title=category.title,
            description="Other task",
            contact_name="Client",
            contact_phone="@client",
            contact_username="client",
        )
    )

    first = await service.cancel_by_client(lead_id=lead.id, actor=user)
    second = await service.cancel_by_client(lead_id=lead.id, actor=user)

    assert first.status == LeadStatus.CANCELLED
    assert second.id == first.id


@pytest.mark.asyncio
async def test_admin_status_change_and_csv_export(session) -> None:
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("consultation")
    user_repo = UserRepository(session)
    client = await user_repo.upsert_telegram_user(
        telegram_id=102,
        username="client",
        first_name="Client",
        last_name=None,
    )
    admin = await user_repo.upsert_telegram_user(
        telegram_id=999,
        username="admin",
        first_name="Admin",
        last_name=None,
        is_admin=True,
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    lead = await service.create_lead(
        LeadCreateInput(
            user_id=client.id,
            category_id=category.id,
            title=category.title,
            description="Need advice",
            contact_name="Client",
            contact_phone="@client",
            contact_username="client",
        )
    )

    updated = await service.change_status(
        lead_id=lead.id,
        status=LeadStatus.IN_PROGRESS,
        actor=admin,
    )
    csv_payload = await service.export_csv()

    assert updated.status == LeadStatus.IN_PROGRESS
    assert "TG-000001" in csv_payload
    assert "consultation" not in csv_payload
    assert "Консультация" in csv_payload


@pytest.mark.asyncio
async def test_admin_take_lead_assigns_and_moves_to_in_progress_idempotently(session) -> None:
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("consultation")
    user_repo = UserRepository(session)
    client = await user_repo.upsert_telegram_user(
        telegram_id=105,
        username="client",
        first_name="Client",
        last_name=None,
    )
    admin = await user_repo.upsert_telegram_user(
        telegram_id=999,
        username="admin",
        first_name="Admin",
        last_name=None,
        is_admin=True,
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    lead = await service.create_lead(
        LeadCreateInput(
            user_id=client.id,
            category_id=category.id,
            title=category.title,
            description="Need advice",
            contact_name="Client",
            contact_phone="@client",
            contact_username="client",
        )
    )

    assigned = await service.assign_to_admin(lead_id=lead.id, admin=admin)
    assigned_again = await service.assign_to_admin(lead_id=lead.id, admin=admin)
    same_status = await service.change_status(
        lead_id=lead.id,
        status=LeadStatus.IN_PROGRESS,
        actor=admin,
    )

    assert assigned.assigned_admin_id == admin.id
    assert assigned.status == LeadStatus.IN_PROGRESS
    assert assigned_again.id == assigned.id
    assert same_status.status == LeadStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_admin_list_filters_by_user_and_date(session) -> None:
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("other")
    user_repo = UserRepository(session)
    client_a = await user_repo.upsert_telegram_user(
        telegram_id=301,
        username="alpha",
        first_name="Alpha",
        last_name=None,
    )
    client_b = await user_repo.upsert_telegram_user(
        telegram_id=302,
        username="beta",
        first_name="Beta",
        last_name=None,
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    lead_a = await service.create_lead(
        LeadCreateInput(
            user_id=client_a.id,
            category_id=category.id,
            title=category.title,
            description="Alpha task",
            contact_name="Alpha",
            contact_phone="@alpha",
            contact_username="alpha",
        )
    )
    await service.create_lead(
        LeadCreateInput(
            user_id=client_b.id,
            category_id=category.id,
            title=category.title,
            description="Beta task",
            contact_name="Beta",
            contact_phone="@beta",
            contact_username="beta",
        )
    )

    filtered_by_user = await service.list_leads(user_query="@alpha")
    filtered_by_date = await service.list_leads(date_from=datetime.now(UTC).date())
    filtered_by_future = await service.list_leads(
        date_from=(datetime.now(UTC) + timedelta(days=1)).date()
    )

    assert [lead.id for lead in filtered_by_user] == [lead_a.id]
    assert len(filtered_by_date) == 2
    assert filtered_by_future == []


@pytest.mark.asyncio
async def test_comments_can_be_public_or_internal(session) -> None:
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("other")
    user_repo = UserRepository(session)
    client = await user_repo.upsert_telegram_user(
        telegram_id=303,
        username="client",
        first_name="Client",
        last_name=None,
    )
    admin = await user_repo.upsert_telegram_user(
        telegram_id=999,
        username="admin",
        first_name="Admin",
        last_name=None,
        is_admin=True,
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    lead = await service.create_lead(
        LeadCreateInput(
            user_id=client.id,
            category_id=category.id,
            title=category.title,
            description="Task",
            contact_name="Client",
            contact_phone="@client",
            contact_username="client",
        )
    )

    await service.add_comment(lead_id=lead.id, admin=admin, text="internal", is_internal=True)
    updated = await service.add_comment(
        lead_id=lead.id,
        admin=admin,
        text="public",
        is_internal=False,
    )

    assert [(comment.text, comment.is_internal) for comment in updated.comments] == [
        ("internal", True),
        ("public", False),
    ]


@pytest.mark.asyncio
async def test_lead_repository_count_by_user(session) -> None:
    """LeadRepository.count_by_user returns number of leads owned by user."""
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("other")
    user_repo = UserRepository(session)
    user_a = await user_repo.upsert_telegram_user(
        telegram_id=401,
        username="user_a",
        first_name="UserA",
        last_name=None,
    )
    user_b = await user_repo.upsert_telegram_user(
        telegram_id=402,
        username="user_b",
        first_name="UserB",
        last_name=None,
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    repo = LeadRepository(session)

    # No leads yet.
    assert await repo.count_by_user(user_a.id) == 0

    await service.create_lead(
        LeadCreateInput(
            user_id=user_a.id,
            category_id=category.id,
            title=category.title,
            description="Task A1",
            contact_name="UserA",
            contact_phone="@user_a",
            contact_username="user_a",
        )
    )
    await service.create_lead(
        LeadCreateInput(
            user_id=user_a.id,
            category_id=category.id,
            title=category.title,
            description="Task A2",
            contact_name="UserA",
            contact_phone="@user_a",
            contact_username="user_a",
        )
    )
    await service.create_lead(
        LeadCreateInput(
            user_id=user_b.id,
            category_id=category.id,
            title=category.title,
            description="Task B1",
            contact_name="UserB",
            contact_phone="@user_b",
            contact_username="user_b",
        )
    )

    assert await repo.count_by_user(user_a.id) == 2
    assert await repo.count_by_user(user_b.id) == 1
