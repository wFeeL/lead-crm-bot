from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import InlineKeyboardMarkup

from app.bot.ui.navigation import set_root_message_id
from app.bot.ui.render import render_screen
from app.bot.ui.screen import Screen


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


async def test_render_first_time_sends_new_message(state: FSMContext):
    bot = MagicMock()
    sent = MagicMock(message_id=555)
    bot.send_message = AsyncMock(return_value=sent)
    bot.edit_message_text = AsyncMock()

    screen = Screen(
        screen_id="main_menu",
        text="Hi",
        keyboard=InlineKeyboardMarkup(inline_keyboard=[]),
    )
    await render_screen(bot=bot, chat_id=42, state=state, screen=screen)

    bot.send_message.assert_awaited_once()
    bot.edit_message_text.assert_not_called()
    data = await state.get_data()
    assert data["root_message_id"] == 555


async def test_render_second_time_edits_existing_root(state: FSMContext):
    await set_root_message_id(state, 100)
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()

    screen = Screen(
        screen_id="faq",
        text="Q",
        keyboard=InlineKeyboardMarkup(inline_keyboard=[]),
    )
    await render_screen(bot=bot, chat_id=42, state=state, screen=screen)

    bot.edit_message_text.assert_awaited_once()
    bot.send_message.assert_not_called()
    call_kwargs = bot.edit_message_text.await_args.kwargs
    assert call_kwargs["chat_id"] == 42
    assert call_kwargs["message_id"] == 100
    assert call_kwargs["text"] == "Q"


async def test_render_falls_back_to_send_when_edit_fails(state: FSMContext):
    """If edit_message_text raises TelegramBadRequest (e.g. message deleted), send a fresh one."""
    await set_root_message_id(state, 100)
    bot = MagicMock()
    # Create a TelegramBadRequest using a mock for the method arg — keeping the test
    # decoupled from aiogram's internal API shape.
    fake_method = MagicMock()
    bot.edit_message_text = AsyncMock(
        side_effect=TelegramBadRequest(method=fake_method, message="message to edit not found")
    )
    sent = MagicMock(message_id=200)
    bot.send_message = AsyncMock(return_value=sent)

    screen = Screen(
        screen_id="x",
        text="y",
        keyboard=InlineKeyboardMarkup(inline_keyboard=[]),
    )
    await render_screen(bot=bot, chat_id=42, state=state, screen=screen)

    bot.edit_message_text.assert_awaited_once()
    bot.send_message.assert_awaited_once()
    data = await state.get_data()
    assert data["root_message_id"] == 200
