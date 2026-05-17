"""Integration tests for the FAQ handler flow."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.routers.user.faq import handle_faq_select
from app.bot.screens.faq import FaqCallback
from app.bot.ui.navigation import get_stack
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


@pytest.fixture
def content():
    return ContentService(ContentService.load(_CONTENT_DIR))


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    fsm = FSMContext(storage=storage, key=key)
    # Simulate user already on FAQ screen.
    await fsm.update_data({"root_message_id": 999, "nav_stack": ["main_menu", "faq"]})
    return fsm


async def test_faq_select_renders_answer_screen(content, state):
    """Selecting FAQ item pushes faq_answer and edits the root message with the answer text."""
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock()
    callback = MagicMock()
    callback.bot = bot
    callback.message = MagicMock(chat=MagicMock(id=42), message_id=999)
    callback.answer = AsyncMock()

    await handle_faq_select(
        callback=callback,
        callback_data=FaqCallback(index=0),
        state=state,
        content=content,
    )

    stack = await get_stack(state)
    assert "faq_answer" in stack
    bot.edit_message_text.assert_awaited_once()
    call_kwargs = bot.edit_message_text.await_args.kwargs
    assert content.faq[0].a in call_kwargs["text"]
    callback.answer.assert_awaited()


async def test_faq_select_second_entry(content, state):
    """Selecting a different FAQ index renders the correct answer."""
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock()
    callback = MagicMock()
    callback.bot = bot
    callback.message = MagicMock(chat=MagicMock(id=42), message_id=999)
    callback.answer = AsyncMock()

    await handle_faq_select(
        callback=callback,
        callback_data=FaqCallback(index=1),
        state=state,
        content=content,
    )

    bot.edit_message_text.assert_awaited_once()
    call_kwargs = bot.edit_message_text.await_args.kwargs
    assert content.faq[1].a in call_kwargs["text"]
    assert content.faq[1].q in call_kwargs["text"]
