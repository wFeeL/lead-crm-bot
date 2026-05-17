"""Integration tests for the my_leads handler flow."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.routers.user.my_leads import handle_lead_detail_action, handle_my_leads
from app.bot.screens.my_leads import MyLeadDetailCallback, MyLeadsCallback
from app.bot.ui.navigation import get_stack
from app.core.config import Settings
from app.core.constants import LeadStatus
from app.db.repositories.forms import FormRepository
from app.db.repositories.users import UserRepository
from app.schemas.lead import LeadCreateInput
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from app.services.leads import LeadService
from sqlalchemy.ext.asyncio import AsyncSession

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


@pytest.fixture
def content():
    return ContentService(ContentService.load(_CONTENT_DIR))


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


@pytest.fixture
async def current_user(session: AsyncSession, content):
    await ensure_seed_data(session, content.bundle)
    await session.commit()
    repo = UserRepository(session)
    return await repo.upsert_telegram_user(
        telegram_id=42,
        username="test_user",
        first_name="Test",
        last_name=None,
        is_admin=False,
    )


def _callback(message_id=999):
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=message_id))
    callback = MagicMock()
    callback.bot = bot
    callback.message = MagicMock(chat=MagicMock(id=42), message_id=message_id)
    callback.answer = AsyncMock()
    return callback


async def test_my_leads_empty_state(content, state, session, current_user):
    """Requesting page 1 for a user with no leads renders empty-state text."""
    await state.update_data({"root_message_id": 999, "nav_stack": ["main_menu"]})
    callback = _callback()

    await handle_my_leads(
        callback=callback,
        callback_data=MyLeadsCallback(action="page", page=1),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    callback.bot.edit_message_text.assert_awaited_once()
    text = callback.bot.edit_message_text.await_args.kwargs["text"]
    assert "пока" in text.lower() or "нет заявок" in text.lower()
    # Stack updated.
    stack = await get_stack(state)
    assert "my_leads" in stack


async def test_my_leads_with_one_lead_shows_list(content, state, session, current_user):
    """One existing lead: page renders the list view with a lead row button."""
    await state.update_data({"root_message_id": 999, "nav_stack": ["main_menu"]})

    # Seed a lead for the user.
    category = await FormRepository(session).get_category_by_slug("other")
    service = LeadService(session, Settings(admin_ids=[999]))
    await service.create_lead(
        LeadCreateInput(
            user_id=current_user.id,
            category_id=category.id,
            title=category.title,
            description="Test lead",
            contact_name="Test",
            contact_phone="@test",
            contact_username="test_user",
        )
    )

    callback = _callback()
    await handle_my_leads(
        callback=callback,
        callback_data=MyLeadsCallback(action="page", page=1),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    callback.bot.edit_message_text.assert_awaited_once()
    text = callback.bot.edit_message_text.await_args.kwargs["text"]
    # Non-empty list renders "Ваши заявки" heading.
    assert "заявк" in text.lower()


async def test_my_leads_open_lead_shows_detail(content, state, session, current_user):
    """Opening an existing lead by ID renders the detail screen."""
    await state.update_data({"root_message_id": 999, "nav_stack": ["main_menu", "my_leads"]})

    category = await FormRepository(session).get_category_by_slug("other")
    service = LeadService(session, Settings(admin_ids=[999]))
    lead = await service.create_lead(
        LeadCreateInput(
            user_id=current_user.id,
            category_id=category.id,
            title=category.title,
            description="Detail test",
            contact_name="Test",
            contact_phone="@test",
            contact_username="test_user",
        )
    )

    callback = _callback()
    await handle_my_leads(
        callback=callback,
        callback_data=MyLeadsCallback(action="open", lead_id=lead.id),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    stack = await get_stack(state)
    assert "my_lead_detail" in stack
    callback.bot.edit_message_text.assert_awaited_once()
    text = callback.bot.edit_message_text.await_args.kwargs["text"]
    assert lead.public_id in text


async def test_my_leads_cancel_lead_pushes_reason_screen(content, state, session, current_user):
    """Clicking cancel on MY_LEAD_DETAIL now pushes the cancel-reason screen instead of
    immediately cancelling the lead (Task 4.5 cancel reason flow)."""
    await state.update_data(
        {"root_message_id": 999, "nav_stack": ["main_menu", "my_leads", "my_lead_detail"]}
    )

    category = await FormRepository(session).get_category_by_slug("other")
    service = LeadService(session, Settings(admin_ids=[999]))
    lead = await service.create_lead(
        LeadCreateInput(
            user_id=current_user.id,
            category_id=category.id,
            title=category.title,
            description="Cancel test",
            contact_name="Test",
            contact_phone="@test",
            contact_username="test_user",
        )
    )
    assert lead.status == LeadStatus.NEW

    callback = _callback()
    await handle_lead_detail_action(
        callback=callback,
        callback_data=MyLeadDetailCallback(action="cancel", lead_id=lead.id),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    # Callback acknowledged.
    callback.answer.assert_awaited()
    # Cancel reason screen rendered (contains the "Отмена заявки" header).
    callback.bot.edit_message_text.assert_awaited_once()
    text = callback.bot.edit_message_text.await_args.kwargs["text"]
    assert "Отмена заявки" in text
    # Lead is NOT yet cancelled — reason hasn't been selected.
    from app.db.repositories.leads import LeadRepository as _LR

    refreshed = await _LR(session).get(lead.id)
    assert refreshed.status == LeadStatus.NEW
