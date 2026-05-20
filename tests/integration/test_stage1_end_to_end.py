"""Stage 1 end-to-end smoke tests — full user & admin journeys."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.routers.admin.menu import (
    on_admin_detail_action,
    on_admin_list_action,
    on_admin_menu_action,
    on_close_reason_action,
)
from app.bot.routers.user.lead_create import (
    on_confirm_action,
    on_contact,
    on_files_action,
    on_pick_category,
    on_text_answer,
    start_lead_create,
)
from app.bot.routers.user.my_leads import handle_lead_detail_action, handle_my_leads
from app.bot.routers.user.support import handle_support_message
from app.bot.screens.admin_close_reason import AdminCloseReasonCallback
from app.bot.screens.admin_lead_detail import AdminDetailCallback
from app.bot.screens.admin_lead_list import AdminLeadListCallback
from app.bot.screens.admin_menu import AdminMenuCallback
from app.bot.screens.cancel_reason import CancelReasonCallback
from app.bot.screens.lead_category import LeadCategoryCallback
from app.bot.screens.lead_confirm import LeadConfirmCallback
from app.bot.screens.lead_files import LeadFilesCallback
from app.bot.screens.my_leads import MyLeadDetailCallback, MyLeadsCallback
from app.bot.states.lead import LeadFormState
from app.bot.states.support import SupportState
from app.core.config import get_settings
from app.core.constants import LeadStatus
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from sqlalchemy.ext.asyncio import AsyncSession

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


# ─── shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def _make_state(chat_id: int = 42):
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=chat_id, user_id=chat_id)
    return FSMContext(storage=storage, key=key)


def _bot():
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    bot.edit_message_text = AsyncMock()
    return bot


def _callback(bot=None, chat_id: int = 42, message_id: int = 999):
    bot = bot or _bot()
    cb = MagicMock()
    cb.bot = bot
    cb.message = MagicMock(chat=MagicMock(id=chat_id), message_id=message_id)
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


def _message(bot, text: str, chat_id: int = 42):
    msg = MagicMock()
    msg.bot = bot
    msg.chat = MagicMock(id=chat_id)
    msg.text = text
    msg.contact = None
    msg.answer = AsyncMock(return_value=MagicMock(delete=AsyncMock()))
    return msg


@pytest.fixture
async def user(session: AsyncSession, content):
    await ensure_seed_data(session, content.bundle)
    await session.commit()
    repo = UserRepository(session)
    return await repo.upsert_telegram_user(
        telegram_id=42, username="user", first_name="User", last_name=None, is_admin=False
    )


@pytest.fixture
async def admin_user(session: AsyncSession, content, monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "999")
    monkeypatch.setenv("BOT_TOKEN", "test")
    get_settings.cache_clear()
    await ensure_seed_data(session, content.bundle)
    await session.commit()
    repo = UserRepository(session)
    u = await repo.upsert_telegram_user(
        telegram_id=999, username="admin", first_name="Admin", last_name=None, is_admin=True
    )
    await session.commit()
    return u


@pytest.fixture
async def client_user(session: AsyncSession, admin_user):
    repo = UserRepository(session)
    u = await repo.upsert_telegram_user(
        telegram_id=100, username="client", first_name="Client", last_name=None, is_admin=False
    )
    await session.commit()
    return u


# ─── helpers ─────────────────────────────────────────────────────────────────


async def _make_lead_via_service(session, user, category_slug="telegram_bot"):
    from app.db.models.category import LeadCategory
    from app.schemas.lead import LeadCreateInput
    from app.services.leads import LeadService
    from sqlalchemy import select

    cat = (
        await session.execute(select(LeadCategory).where(LeadCategory.slug == category_slug))
    ).scalar_one()
    settings = get_settings()
    svc = LeadService(session, settings)
    lead = await svc.create_lead(
        LeadCreateInput(
            user_id=user.id,
            category_id=cat.id,
            title="Test",
            description="desc",
            contact_name="User",
            contact_phone="+7",
            contact_username="user",
            answers=[],
            files=[],
            source="bot",
        )
    )
    await session.commit()
    return lead


# ─── Test 1: full user journey — create → my_leads → cancel ──────────────────


async def test_full_user_journey_create_to_my_leads(content, session: AsyncSession, user):
    """User creates a lead via the form, opens My Leads, sees the lead, and cancels it."""
    state = _make_state()
    await state.update_data({"root_message_id": 999, "nav_stack": ["main_menu"]})

    with patch("app.bot.routers.user.lead_create.NotificationService") as mock_cls:
        mock_cls.return_value = MagicMock(notify_new_lead=AsyncMock())

        # Start lead creation.
        await start_lead_create(
            bot=_bot(), chat_id=42, state=state, session=session, content=content
        )
        assert await state.get_state() == LeadFormState.choosing_category.state

        # Pick category.
        await on_pick_category(
            callback=_callback(),
            callback_data=LeadCategoryCallback(slug="telegram_bot"),
            state=state,
            session=session,
            content=content,
        )
        assert await state.get_state() == LeadFormState.answering_questions.state

        # Answer 3 questions.
        data = await state.get_data()
        for i in range(len(data["questions"])):
            await on_text_answer(
                message=_message(_bot(), f"Ответ {i + 1}"),
                state=state,
                content=content,
            )

        assert await state.get_state() == LeadFormState.uploading_files.state

        # Skip files.
        await on_files_action(
            callback=_callback(),
            callback_data=LeadFilesCallback(action="continue"),
            state=state,
            content=content,
        )
        assert await state.get_state() == LeadFormState.entering_contact.state

        # Enter contact.
        await on_contact(
            message=_message(_bot(), "+7 900 000 0000"),
            state=state,
            content=content,
        )
        assert await state.get_state() == LeadFormState.confirming.state

        # Submit.
        await on_confirm_action(
            callback=_callback(),
            callback_data=LeadConfirmCallback(action="submit"),
            state=state,
            session=session,
            current_user=user,
            content=content,
        )

    assert await state.get_state() is None

    # Check lead in DB.
    repo = LeadRepository(session)
    leads = await repo.list_by_user(user.id, limit=10, offset=0)
    assert len(leads) == 1
    lead = leads[0]
    assert lead.status == LeadStatus.NEW

    # Open My Leads.
    await state.update_data({"root_message_id": 999, "nav_stack": ["main_menu"]})
    cb = _callback()
    await handle_my_leads(
        callback=cb,
        callback_data=MyLeadsCallback(action="page", page=1),
        state=state,
        content=content,
        session=session,
        current_user=user,
    )
    cb.bot.edit_message_text.assert_awaited()
    text = cb.bot.edit_message_text.await_args.kwargs["text"]
    assert "заявк" in text.lower()

    # Cancel the lead.
    await state.update_data({"nav_stack": ["main_menu", "my_leads", "my_lead_detail"]})
    cb2 = _callback()
    await handle_lead_detail_action(
        callback=cb2,
        callback_data=MyLeadDetailCallback(action="cancel", lead_id=lead.id),
        state=state,
        content=content,
        session=session,
        current_user=user,
    )
    cb2.answer.assert_awaited()
    # Cancel-reason screen is sent fresh (force_new=True for input prompts;
    # see fix #5 in the audit).
    cb2.bot.send_message.assert_awaited()

    # Pick reason index 0.
    from app.bot.routers.user.my_leads import handle_cancel_reason
    from app.bot.screens.cancel_reason import MY_LEAD_CANCEL_REASON_SCREEN_ID
    from app.bot.ui.navigation import push

    await push(state, MY_LEAD_CANCEL_REASON_SCREEN_ID)
    cb3 = _callback()
    await handle_cancel_reason(
        callback=cb3,
        callback_data=CancelReasonCallback(action="pick", lead_id=lead.id, index=0),
        state=state,
        content=content,
        session=session,
        current_user=user,
    )

    refreshed = await repo.get(lead.id)
    assert refreshed.status == LeadStatus.CANCELLED


# ─── Test 2: admin journey — new → in_progress → done ───────────────────────


async def test_full_admin_journey_new_to_done(
    content, session: AsyncSession, admin_user, client_user
):
    """Admin opens a new lead, moves it to in_progress, then done with a close reason."""
    lead = await _make_lead_via_service(session, client_user)

    state = _make_state(chat_id=999)
    await state.update_data({"root_message_id": 999, "nav_stack": ["admin_menu"]})

    # Show 'new' list.
    with patch("app.bot.routers.admin.menu.NotificationService") as mock_cls:
        mock_cls.return_value = MagicMock(notify_client_status=AsyncMock())

        cb = _callback(chat_id=999)
        await on_admin_menu_action(
            callback=cb,
            callback_data=AdminMenuCallback(action="new"),
            state=state,
            content=content,
            session=session,
            current_user=admin_user,
        )
        cb.bot.edit_message_text.assert_awaited()

        # Open lead.
        await state.update_data(admin_filter={"status": "new", "hot": False, "label": "Новые"})
        cb2 = _callback(chat_id=999)
        await on_admin_list_action(
            callback=cb2,
            callback_data=AdminLeadListCallback(action="open", lead_id=lead.id, page=1),
            state=state,
            content=content,
            session=session,
            current_user=admin_user,
        )
        data = await state.get_data()
        assert "admin_lead_detail" in data["nav_stack"]

        # Move to in_progress.
        cb3 = _callback(chat_id=999)
        await on_admin_detail_action(
            callback=cb3,
            callback_data=AdminDetailCallback(
                action="set_status", lead_id=lead.id, value="in_progress"
            ),
            state=state,
            content=content,
            session=session,
            current_user=admin_user,
        )
        refreshed = await LeadRepository(session).get(lead.id)
        assert refreshed.status == "in_progress"

        # Set done — should push close_reason screen.
        cb4 = _callback(chat_id=999)
        await on_admin_detail_action(
            callback=cb4,
            callback_data=AdminDetailCallback(action="set_status", lead_id=lead.id, value="done"),
            state=state,
            content=content,
            session=session,
            current_user=admin_user,
        )
        data2 = await state.get_data()
        assert "admin_close_reason" in data2["nav_stack"]

        # Pick close reason index 0.
        cb5 = _callback(chat_id=999)
        await on_close_reason_action(
            callback=cb5,
            callback_data=AdminCloseReasonCallback(
                action="pick", lead_id=lead.id, target_status="done", index=0
            ),
            state=state,
            content=content,
            session=session,
            current_user=admin_user,
        )

    done_lead = await LeadRepository(session).get(lead.id)
    assert done_lead.status == "done"
    assert done_lead.close_reason is not None


# ─── Test 3: repeat creates new lead with source='repeat' ────────────────────


async def test_repeat_lead_creates_new_with_repeat_source(content, session: AsyncSession, user):
    """Clicking Repeat on MY_LEAD_DETAIL pre-fills confirm screen; submitting source=repeat."""
    from app.bot.routers.user.my_leads import handle_lead_detail_action as hda

    original = await _make_lead_via_service(session, user)

    state = _make_state()
    await state.update_data(
        {"root_message_id": 999, "nav_stack": ["main_menu", "my_leads", "my_lead_detail"]}
    )

    cb = _callback()
    await hda(
        callback=cb,
        callback_data=MyLeadDetailCallback(action="repeat", lead_id=original.id),
        state=state,
        content=content,
        session=session,
        current_user=user,
    )

    assert await state.get_state() == LeadFormState.confirming.state
    data = await state.get_data()
    assert data.get("source") == "repeat"

    # Submit the pre-filled form.
    with patch("app.bot.routers.user.lead_create.NotificationService") as mock_cls:
        mock_cls.return_value = MagicMock(notify_new_lead=AsyncMock())
        cb2 = _callback()
        await on_confirm_action(
            callback=cb2,
            callback_data=LeadConfirmCallback(action="submit"),
            state=state,
            session=session,
            current_user=user,
            content=content,
        )

    repo = LeadRepository(session)
    leads = await repo.list_by_user(user.id, limit=10, offset=0)
    sources = [lead.source for lead in leads]
    assert "repeat" in sources


# ─── Test 4: support via main menu creates lead with source='support' ─────────


async def test_support_lead_via_main_menu_button(content, session: AsyncSession, user):
    """User sends a support message; a lead with source='support' is created."""
    state = _make_state()
    await state.set_state(SupportState.writing_message)
    await state.update_data(
        {"root_message_id": 999, "nav_stack": ["main_menu", "support", "support_writing"]}
    )

    bot = _bot()
    msg = _message(bot, "Нужна помощь с заявкой")

    await handle_support_message(
        message=msg,
        state=state,
        content=content,
        session=session,
        current_user=user,
    )

    assert await state.get_state() is None

    repo = LeadRepository(session)
    leads = await repo.list_by_user(user.id)
    assert len(leads) == 1
    assert leads[0].source == "support"
    assert leads[0].category.slug == "support"


# ─── Test 5: EscapeMiddleware clears FSM and stops handler ───────────────────


async def test_escape_middleware_full_cycle(content, session: AsyncSession, user):
    """/cancel mid lead-creation clears FSM and does NOT call the downstream handler."""
    from unittest.mock import AsyncMock as AM

    from aiogram.types import Message
    from app.bot.middlewares.escape import EscapeMiddleware

    state = _make_state()
    await state.update_data({"root_message_id": 999, "nav_stack": ["main_menu"]})

    # Start lead creation to put FSM into an active state.
    await start_lead_create(bot=_bot(), chat_id=42, state=state, session=session, content=content)
    assert await state.get_state() == LeadFormState.choosing_category.state

    # Simulate /cancel message through EscapeMiddleware.
    handler = AM()
    msg = MagicMock(spec=Message)
    msg.text = "/cancel"
    await EscapeMiddleware()(handler, msg, {"state": state})

    assert await state.get_state() is None
    handler.assert_not_awaited()
