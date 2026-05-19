"""Integration tests for Tier 2.A/B: admin search + date-range filter."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.core.config import Settings
from app.db.models.lead import Lead
from app.db.repositories.forms import FormRepository
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.schemas.lead import LeadCreateInput
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from app.services.leads import LeadService
from app.services.period import period_label, resolve_period

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"
_BUNDLE = ContentService.load(_CONTENT_DIR)


async def _seed_user_lead(
    session,
    *,
    telegram_id: int,
    username: str | None,
    phone: str | None,
    contact_username: str | None = None,
):
    await ensure_seed_data(session, _BUNDLE)
    category = await FormRepository(session).get_category_by_slug("other")
    user = await UserRepository(session).upsert_telegram_user(
        telegram_id=telegram_id,
        username=username,
        first_name="Client",
        last_name=None,
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    lead = await service.create_lead(
        LeadCreateInput(
            user_id=user.id,
            category_id=category.id,
            title="t",
            description="d",
            contact_name="Client",
            contact_phone=phone,
            contact_username=contact_username,
        )
    )
    return user, lead


# ---------- Search ----------


@pytest.mark.asyncio
async def test_search_by_phone_partial_match(session):
    _, lead = await _seed_user_lead(
        session, telegram_id=601, username="alice", phone="+79991234567"
    )
    repo = LeadRepository(session)
    hits = await repo.search(query="9991234")
    assert any(h.id == lead.id for h in hits)


@pytest.mark.asyncio
async def test_search_by_username_with_at_prefix(session):
    _, lead = await _seed_user_lead(
        session, telegram_id=602, username="bob_smith", phone="+79990000001"
    )
    repo = LeadRepository(session)
    hits = await repo.search(query="@bob")
    assert any(h.id == lead.id for h in hits)


@pytest.mark.asyncio
async def test_search_by_public_id(session):
    _, lead = await _seed_user_lead(session, telegram_id=603, username="c", phone="+7000")
    repo = LeadRepository(session)
    hits = await repo.search(query=lead.public_id)
    assert any(h.id == lead.id for h in hits)


@pytest.mark.asyncio
async def test_search_by_telegram_id(session):
    user, lead = await _seed_user_lead(session, telegram_id=604, username="d", phone="+7001")
    repo = LeadRepository(session)
    hits = await repo.search(query=str(user.telegram_id))
    assert any(h.id == lead.id for h in hits)


@pytest.mark.asyncio
async def test_search_excludes_deleted_leads(session):
    _, lead = await _seed_user_lead(
        session, telegram_id=605, username="erika", phone="+79995554433"
    )
    admin = await UserRepository(session).upsert_telegram_user(
        telegram_id=999, username="admin", first_name="A", last_name=None, is_admin=True
    )
    service = LeadService(session, Settings(admin_ids=[999]))
    await service.delete_lead(lead_id=lead.id, actor=admin)
    repo = LeadRepository(session)
    hits = await repo.search(query="erika")
    assert all(h.id != lead.id for h in hits)


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(session):
    await _seed_user_lead(session, telegram_id=606, username="f", phone="+7002")
    repo = LeadRepository(session)
    assert await repo.search(query="") == []
    assert await repo.search(query="   ") == []


@pytest.mark.asyncio
async def test_count_search_matches_search(session):
    await _seed_user_lead(session, telegram_id=607, username="goldfish", phone="+79994441111")
    await _seed_user_lead(session, telegram_id=608, username="goldenboy", phone="+79994441112")
    repo = LeadRepository(session)
    hits = await repo.search(query="gold", limit=100)
    total = await repo.count_search(query="gold")
    assert total == len(hits) >= 2


# ---------- Date range / period ----------


@pytest.mark.asyncio
async def test_list_by_filter_respects_date_from(session):
    _, lead = await _seed_user_lead(session, telegram_id=701, username="g", phone="+7003")
    # Backdate one lead by 10 days.
    lead_orm = await session.get(Lead, lead.id)
    lead_orm.created_at = datetime.now(UTC) - timedelta(days=10)
    await session.flush()

    repo = LeadRepository(session)
    # Last 7 days excludes the backdated lead.
    date_from = datetime.now(UTC) - timedelta(days=7)
    recent = await repo.list_by_filter(date_from=date_from)
    assert all(item.id != lead.id for item in recent)
    # 30-day window includes it.
    long_from = datetime.now(UTC) - timedelta(days=30)
    longer = await repo.list_by_filter(date_from=long_from)
    assert any(item.id == lead.id for item in longer)


@pytest.mark.asyncio
async def test_count_by_filter_respects_date_to(session):
    await _seed_user_lead(session, telegram_id=702, username="h", phone="+7004")
    repo = LeadRepository(session)
    yesterday_end = datetime.now(UTC).replace(hour=0, minute=0, second=0) - timedelta(seconds=1)
    # No leads expected before today's midnight.
    assert await repo.count_by_filter(date_to=yesterday_end) == 0
    # All leads counted with no upper bound.
    assert await repo.count_by_filter() >= 1


# ---------- Period helper ----------


def test_resolve_period_today_returns_today_range():
    start, end = resolve_period("today")
    assert start is not None and end is not None
    assert start.date() == end.date() == datetime.now(UTC).date()


def test_resolve_period_all_returns_none():
    assert resolve_period("all") == (None, None)
    assert resolve_period(None) == (None, None)
    assert resolve_period("") == (None, None)


def test_resolve_period_week_is_seven_days():
    start, end = resolve_period("week")
    assert end is not None
    assert start is not None
    delta = end.date() - start.date()
    assert delta.days == 6


def test_resolve_period_yesterday_is_one_day():
    start, end = resolve_period("yesterday")
    assert start is not None and end is not None
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    assert start.date() == end.date() == yesterday


def test_resolve_period_unknown_falls_back_to_no_filter():
    assert resolve_period("decade") == (None, None)


def test_period_label_returns_human_string():
    assert period_label("today") == "Сегодня"
    assert period_label("week") == "Неделя"
    assert period_label(None) == "Все время"
    assert period_label("unknown") == "Все время"
