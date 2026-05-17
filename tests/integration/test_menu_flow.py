"""Integration tests for the main-menu handler flows."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.routers.user.menu import handle_main_menu, render_and_show_main_menu
from app.bot.screens.main_menu import MainMenuCallback
from app.bot.ui.navigation import get_stack
from app.db.repositories.users import UserRepository
from app.services.content import ContentService
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
async def current_user(session: AsyncSession):
    repo = UserRepository(session)
    return await repo.upsert_telegram_user(
        telegram_id=42,
        username="test_user",
        first_name="Test",
        last_name=None,
        is_admin=False,
    )


def _bot_with_send():
    bot = MagicMock()
    sent = MagicMock(message_id=999)
    bot.send_message = AsyncMock(return_value=sent)
    bot.edit_message_text = AsyncMock()
    return bot


def _callback(bot, message_id=999):
    callback = MagicMock()
    callback.bot = bot
    callback.message = MagicMock(chat=MagicMock(id=42), message_id=message_id)
    callback.answer = AsyncMock()
    return callback


async def test_render_and_show_main_menu_sends_message(content, state):
    """Fresh state: render_and_show_main_menu fires bot.send_message and
    stores root_message_id + nav_stack in FSM data."""
    bot = _bot_with_send()
    await render_and_show_main_menu(
        bot=bot, chat_id=42, state=state, content=content, leads_count=0
    )
    bot.send_message.assert_awaited_once()
    data = await state.get_data()
    assert data["root_message_id"] == 999
    assert data["nav_stack"] == ["main_menu"]


async def test_handle_main_menu_my_leads_button(content, state, session, current_user):
    """MainMenuCallback(action='my_leads') pushes my_leads onto the nav stack."""
    await state.update_data({"root_message_id": 999, "nav_stack": ["main_menu"]})
    bot = _bot_with_send()
    callback = _callback(bot)

    await handle_main_menu(
        callback=callback,
        callback_data=MainMenuCallback(action="my_leads"),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    stack = await get_stack(state)
    assert "my_leads" in stack
    assert bot.edit_message_text.await_count + bot.send_message.await_count >= 1
    callback.answer.assert_awaited()


async def test_handle_main_menu_support_button(content, state, session, current_user):
    """MainMenuCallback(action='support') pushes support onto the nav stack."""
    await state.update_data({"root_message_id": 999, "nav_stack": ["main_menu"]})
    bot = _bot_with_send()
    callback = _callback(bot)

    await handle_main_menu(
        callback=callback,
        callback_data=MainMenuCallback(action="support"),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    stack = await get_stack(state)
    assert "support" in stack
    callback.answer.assert_awaited()


async def test_handle_main_menu_faq_button(content, state, session, current_user):
    """MainMenuCallback(action='faq') pushes faq onto the nav stack."""
    await state.update_data({"root_message_id": 999, "nav_stack": ["main_menu"]})
    bot = _bot_with_send()
    callback = _callback(bot)

    await handle_main_menu(
        callback=callback,
        callback_data=MainMenuCallback(action="faq"),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    stack = await get_stack(state)
    assert "faq" in stack
    callback.answer.assert_awaited()


async def test_handle_main_menu_create_lead_starts_flow(content, state, session, current_user):
    """MainMenuCallback(action='create_lead') pushes lead_category onto the nav stack."""
    await state.update_data({"root_message_id": 999, "nav_stack": ["main_menu"]})
    bot = _bot_with_send()
    callback = _callback(bot)

    await handle_main_menu(
        callback=callback,
        callback_data=MainMenuCallback(action="create_lead"),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    stack = await get_stack(state)
    assert "lead_category" in stack
    callback.answer.assert_awaited()
