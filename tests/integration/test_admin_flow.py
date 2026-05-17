"""Integration tests for the admin FSM flow."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.routers.admin.menu import (
    admin_command,
    on_admin_detail_action,
    on_admin_list_action,
    on_admin_menu_action,
    on_close_reason_action,
)
from app.bot.screens.admin_close_reason import AdminCloseReasonCallback
from app.bot.screens.admin_lead_detail import AdminDetailCallback
from app.bot.screens.admin_lead_list import AdminLeadListCallback
from app.bot.screens.admin_menu import AdminMenuCallback
from app.core.config import get_settings
from app.db.models.category import LeadCategory
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.schemas.lead import LeadCreateInput
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from app.services.leads import LeadService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


@pytest.fixture
def content():
    return ContentService(ContentService.load(_CONTENT_DIR))


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    ctx = FSMContext(storage=storage, key=key)
    await ctx.update_data({"root_message_id": 999})
    return ctx


@pytest.fixture
async def admin_user(session: AsyncSession, content, monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "999")
    monkeypatch.setenv("BOT_TOKEN", "test")
    get_settings.cache_clear()
    await ensure_seed_data(session, content.bundle)
    await session.commit()
    repo = UserRepository(session)
    user = await repo.upsert_telegram_user(
        telegram_id=999,
        username="admin_user",
        first_name="Admin",
        last_name=None,
        is_admin=True,
    )
    await session.commit()
    return user


@pytest.fixture
async def client_user(session: AsyncSession, admin_user):
    repo = UserRepository(session)
    user = await repo.upsert_telegram_user(
        telegram_id=100,
        username="client",
        first_name="Client",
        last_name=None,
        is_admin=False,
    )
    await session.commit()
    return user


async def _make_lead(session: AsyncSession, client_user, *, category_slug="telegram_bot"):
    """Helper: create a lead in the DB via LeadService."""
    cat = (
        await session.execute(
            select(LeadCategory).where(LeadCategory.slug == category_slug)
        )
    ).scalar_one()
    settings = get_settings()
    service = LeadService(session, settings)
    payload = LeadCreateInput(
        user_id=client_user.id,
        category_id=cat.id,
        title="Test",
        description="Test lead",
        contact_name="Client",
        contact_phone="+7",
        contact_username="client",
        answers=[],
        files=[],
        source="bot",
    )
    lead = await service.create_lead(payload)
    await session.commit()
    return lead


def _bot():
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    bot.edit_message_text = AsyncMock()
    return bot


def _callback(bot=None, message_id=999):
    bot = bot or _bot()
    cb = MagicMock()
    cb.bot = bot
    cb.message = MagicMock(
        chat=MagicMock(id=42),
        message_id=message_id,
        answer=AsyncMock(),
    )
    cb.answer = AsyncMock()
    return cb


# ---------------------------------------------------------------------------
# Test 1: /admin renders the admin menu
# ---------------------------------------------------------------------------


async def test_admin_command_renders_admin_menu(content, state, session, admin_user):
    """The /admin command renders the admin menu for an admin user."""
    bot = _bot()
    message = MagicMock()
    message.bot = bot
    message.chat = MagicMock(id=42)
    message.answer = AsyncMock()

    await admin_command(
        message=message,
        state=state,
        content=content,
        session=session,
        current_user=admin_user,
    )

    # Must have sent or edited a message (render_screen picks one path).
    assert bot.send_message.await_count + bot.edit_message_text.await_count >= 1


# ---------------------------------------------------------------------------
# Test 2: admin menu callback renders lead list
# ---------------------------------------------------------------------------


async def test_admin_menu_callback_renders_lead_list(
    content, state, session, admin_user, client_user
):
    """Pressing 'new' in admin menu transitions to a lead list screen."""
    await _make_lead(session, client_user)
    await state.update_data({"root_message_id": 999, "nav_stack": ["admin_menu"]})

    bot = _bot()
    cb = _callback(bot)

    await on_admin_menu_action(
        callback=cb,
        callback_data=AdminMenuCallback(action="new"),
        state=state,
        content=content,
        session=session,
        current_user=admin_user,
    )

    bot.edit_message_text.assert_awaited()


# ---------------------------------------------------------------------------
# Test 3: opening a lead from the list pushes detail screen
# ---------------------------------------------------------------------------


async def test_admin_list_open_renders_detail(content, state, session, admin_user, client_user):
    """Opening a lead from the list pushes admin_lead_detail onto the nav stack."""
    lead = await _make_lead(session, client_user)
    await state.update_data({
        "root_message_id": 999,
        "nav_stack": ["admin_menu", "admin_lead_list"],
        "admin_filter": {"status": "new", "hot": False, "label": "Новые"},
    })

    bot = _bot()
    cb = _callback(bot)

    await on_admin_list_action(
        callback=cb,
        callback_data=AdminLeadListCallback(action="open", lead_id=lead.id, page=1),
        state=state,
        content=content,
        session=session,
        current_user=admin_user,
    )

    data = await state.get_data()
    assert "admin_lead_detail" in data["nav_stack"]


# ---------------------------------------------------------------------------
# Test 4: non-terminal status change updates status in DB
# ---------------------------------------------------------------------------


async def test_admin_detail_set_status_non_terminal_changes_status(
    content, state, session, admin_user, client_user
):
    """Setting 'contacted' (non-terminal) updates the lead status immediately."""
    lead = await _make_lead(session, client_user)
    await state.update_data({
        "root_message_id": 999,
        "nav_stack": ["admin_menu", "admin_lead_list", "admin_lead_detail"],
    })

    bot = _bot()
    cb = _callback(bot)

    with patch("app.bot.routers.admin.menu.NotificationService") as mock_notifier_cls:
        mock_notifier = MagicMock()
        mock_notifier.notify_client_status = AsyncMock()
        mock_notifier_cls.return_value = mock_notifier

        await on_admin_detail_action(
            callback=cb,
            callback_data=AdminDetailCallback(
                action="set_status", lead_id=lead.id, value="contacted"
            ),
            state=state,
            content=content,
            session=session,
            current_user=admin_user,
        )

    repo = LeadRepository(session)
    refreshed = await repo.get(lead.id)
    assert refreshed.status == "contacted"


# ---------------------------------------------------------------------------
# Test 5: setting terminal status 'rejected' pushes close_reason screen
# ---------------------------------------------------------------------------


async def test_admin_detail_set_status_rejected_pushes_close_reason(
    content, state, session, admin_user, client_user
):
    """Setting 'rejected' pushes admin_close_reason onto the nav stack without changing status."""
    lead = await _make_lead(session, client_user)
    await state.update_data({
        "root_message_id": 999,
        "nav_stack": ["admin_menu", "admin_lead_list", "admin_lead_detail"],
    })

    bot = _bot()
    cb = _callback(bot)

    await on_admin_detail_action(
        callback=cb,
        callback_data=AdminDetailCallback(
            action="set_status", lead_id=lead.id, value="rejected"
        ),
        state=state,
        content=content,
        session=session,
        current_user=admin_user,
    )

    data = await state.get_data()
    assert "admin_close_reason" in data["nav_stack"]
    # Status must NOT be changed yet — awaiting close reason.
    repo = LeadRepository(session)
    refreshed = await repo.get(lead.id)
    assert refreshed.status == "new"


# ---------------------------------------------------------------------------
# Test 6: picking a close reason persists it and sets rejected status
# ---------------------------------------------------------------------------


async def test_admin_close_reason_pick_persists_reason_and_changes_status(
    content, state, session, admin_user, client_user
):
    """Picking a predefined close reason finalises the rejection with that reason."""
    lead = await _make_lead(session, client_user)
    await state.update_data({
        "root_message_id": 999,
        "nav_stack": [
            "admin_menu",
            "admin_lead_list",
            "admin_lead_detail",
            "admin_close_reason",
        ],
    })

    bot = _bot()
    cb = _callback(bot)

    with patch("app.bot.routers.admin.menu.NotificationService") as mock_notifier_cls:
        mock_notifier = MagicMock()
        mock_notifier.notify_client_status = AsyncMock()
        mock_notifier_cls.return_value = mock_notifier

        await on_close_reason_action(
            callback=cb,
            callback_data=AdminCloseReasonCallback(
                action="pick",
                lead_id=lead.id,
                target_status="rejected",
                index=0,
            ),
            state=state,
            content=content,
            session=session,
            current_user=admin_user,
        )

    repo = LeadRepository(session)
    refreshed = await repo.get(lead.id)
    assert refreshed.status == "rejected"
    assert refreshed.close_reason is not None
    assert refreshed.close_reason == content.texts.close_reasons.rejected[0]


# ---------------------------------------------------------------------------
# Test 7: set_priority updates the priority field
# ---------------------------------------------------------------------------


async def test_admin_detail_set_priority_updates_priority(
    content, state, session, admin_user, client_user
):
    """Setting priority 'urgent' updates the lead priority in the DB."""
    lead = await _make_lead(session, client_user)
    await state.update_data({
        "root_message_id": 999,
        "nav_stack": ["admin_lead_detail"],
    })

    bot = _bot()
    cb = _callback(bot)

    await on_admin_detail_action(
        callback=cb,
        callback_data=AdminDetailCallback(
            action="set_priority", lead_id=lead.id, value="urgent"
        ),
        state=state,
        content=content,
        session=session,
        current_user=admin_user,
    )

    repo = LeadRepository(session)
    refreshed = await repo.get(lead.id)
    assert refreshed.priority == "urgent"


# ---------------------------------------------------------------------------
# Test 8: assign_me sets assigned_admin_id
# ---------------------------------------------------------------------------


async def test_admin_detail_assign_me_when_unassigned(
    content, state, session, admin_user, client_user
):
    """assign_me assigns the current admin when no admin is yet assigned."""
    lead = await _make_lead(session, client_user)
    assert lead.assigned_admin_id is None

    await state.update_data({
        "root_message_id": 999,
        "nav_stack": ["admin_lead_detail"],
    })

    bot = _bot()
    cb = _callback(bot)

    await on_admin_detail_action(
        callback=cb,
        callback_data=AdminDetailCallback(action="assign_me", lead_id=lead.id),
        state=state,
        content=content,
        session=session,
        current_user=admin_user,
    )

    repo = LeadRepository(session)
    refreshed = await repo.get(lead.id)
    assert refreshed.assigned_admin_id == admin_user.id


# ---------------------------------------------------------------------------
# Test 9: non-admin is blocked with an alert
# ---------------------------------------------------------------------------


async def test_admin_unauthorized_blocked(content, state, session, client_user):
    """Non-admin receives 'Недостаточно прав.' alert when triggering admin actions."""
    bot = _bot()
    cb = _callback(bot)

    await on_admin_menu_action(
        callback=cb,
        callback_data=AdminMenuCallback(action="new"),
        state=state,
        content=content,
        session=session,
        current_user=client_user,
    )

    cb.answer.assert_awaited_with("Недостаточно прав.", show_alert=True)
