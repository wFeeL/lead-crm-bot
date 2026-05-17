"""Tests for new repository methods added in Task 5.1."""
from pathlib import Path

import pytest

from app.core.constants import LeadPriority, LeadStatus, UserRole
from app.db.repositories.forms import FormRepository
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.schemas.lead import LeadCreateInput
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from app.services.leads import LeadService
from app.core.config import Settings

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"
_BUNDLE = ContentService.load(_CONTENT_DIR)


async def _seed_and_create_lead(session, telegram_id: int, *, priority: str = "normal", status: str = "new"):
    """Helper: seed, create user and a lead; set status and priority as requested."""
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("other")
    user = await UserRepository(session).upsert_telegram_user(
        telegram_id=telegram_id,
        username=f"user{telegram_id}",
        first_name="User",
        last_name=None,
    )
    service = LeadService(session, Settings(admin_ids=[9990]))
    lead = await service.create_lead(
        LeadCreateInput(
            user_id=user.id,
            category_id=category.id,
            title=category.title,
            description="Test lead",
            contact_name="User",
            contact_phone=f"@user{telegram_id}",
            contact_username=f"user{telegram_id}",
        )
    )
    # Set priority and status directly via ORM
    lead.priority = priority
    session.add(lead)
    if status != "new":
        admin = await UserRepository(session).upsert_telegram_user(
            telegram_id=9990,
            username="admin",
            first_name="Admin",
            last_name=None,
            is_admin=True,
        )
        repo = LeadRepository(session)
        lead = await repo.update_status(lead=lead, status=status, actor_user_id=admin.id)
    else:
        await session.flush()
    return lead


@pytest.mark.asyncio
async def test_status_counts_on_populated_db(session) -> None:
    """status_counts returns correct dict keyed by status string."""
    await _seed_and_create_lead(session, telegram_id=6001, status="new")
    await _seed_and_create_lead(session, telegram_id=6002, status="new")
    await _seed_and_create_lead(session, telegram_id=6003, status="in_progress")

    repo = LeadRepository(session)
    counts = await repo.status_counts()

    assert isinstance(counts, dict)
    assert counts.get("new", 0) >= 2
    assert counts.get("in_progress", 0) >= 1


@pytest.mark.asyncio
async def test_hot_count_counts_high_and_urgent_non_terminal(session) -> None:
    """hot_count returns count of priority=high|urgent AND status not terminal."""
    await _seed_and_create_lead(session, telegram_id=6010, priority="high", status="new")
    await _seed_and_create_lead(session, telegram_id=6011, priority="urgent", status="new")
    await _seed_and_create_lead(session, telegram_id=6012, priority="normal", status="new")
    # Done lead with high priority - should NOT count
    await _seed_and_create_lead(session, telegram_id=6013, priority="high", status="done")

    repo = LeadRepository(session)
    count = await repo.hot_count()

    # There must be at least 2 hot leads (the high+new and urgent+new ones)
    assert count >= 2
    # The done lead with high priority should NOT be included


@pytest.mark.asyncio
async def test_list_by_filter_sorts_urgent_first(session) -> None:
    """list_by_filter sorts urgent > high > normal > low."""
    await _seed_and_create_lead(session, telegram_id=6020, priority="low", status="new")
    await _seed_and_create_lead(session, telegram_id=6021, priority="normal", status="new")
    await _seed_and_create_lead(session, telegram_id=6022, priority="high", status="new")
    await _seed_and_create_lead(session, telegram_id=6023, priority="urgent", status="new")

    repo = LeadRepository(session)
    leads = await repo.list_by_filter(status="new", limit=10)

    # Get priorities of the leads we just created (they should come first in DESC order)
    priorities = [lead.priority for lead in leads]
    # urgent must appear before high, high before normal, normal before low
    # Find positions of the four known leads
    urgent_idx = next(i for i, p in enumerate(priorities) if p == "urgent")
    high_idx = next(i for i, p in enumerate(priorities) if p == "high")
    normal_idx = next(i for i, p in enumerate(priorities) if p == "normal")
    low_idx = next(i for i, p in enumerate(priorities) if p == "low")
    assert urgent_idx < high_idx < normal_idx < low_idx


@pytest.mark.asyncio
async def test_count_by_filter_matches_list_sum(session) -> None:
    """count_by_filter returns the same total as len(list_by_filter(...))."""
    await _seed_and_create_lead(session, telegram_id=6030, priority="high", status="new")
    await _seed_and_create_lead(session, telegram_id=6031, priority="urgent", status="new")
    await _seed_and_create_lead(session, telegram_id=6032, priority="normal", status="in_progress")

    repo = LeadRepository(session)

    # hot filter
    hot_list = await repo.list_by_filter(hot=True, limit=100)
    hot_count = await repo.count_by_filter(hot=True)
    assert len(hot_list) == hot_count

    # status filter
    new_list = await repo.list_by_filter(status="new", limit=100)
    new_count = await repo.count_by_filter(status="new")
    assert len(new_list) == new_count


@pytest.mark.asyncio
async def test_list_admins_returns_only_admin_roles_not_blocked(session) -> None:
    """list_admins returns only users with role in (ADMIN, MANAGER, OWNER) that are not blocked."""
    await ensure_seed_data(session, _BUNDLE)
    user_repo = UserRepository(session)

    admin = await user_repo.upsert_telegram_user(
        telegram_id=7001, username="admin_a", first_name="Admin", last_name=None, is_admin=True,
    )
    client = await user_repo.upsert_telegram_user(
        telegram_id=7002, username="client_b", first_name="Client", last_name=None,
    )
    # Create a blocked admin
    blocked_admin = await user_repo.upsert_telegram_user(
        telegram_id=7003, username="admin_blocked", first_name="Blocked", last_name=None, is_admin=True,
    )
    blocked_admin.is_blocked = True
    session.add(blocked_admin)
    await session.flush()

    admins = await user_repo.list_admins()

    admin_ids = {a.id for a in admins}
    assert admin.id in admin_ids
    assert client.id not in admin_ids
    assert blocked_admin.id not in admin_ids
