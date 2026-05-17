"""Integration tests for the support handler flow."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.routers.user.support import handle_support_action, handle_support_message
from app.bot.screens.support import SupportCallback
from app.bot.states.support import SupportState
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
    fsm = FSMContext(storage=storage, key=key)
    await fsm.update_data({"root_message_id": 999, "nav_stack": ["main_menu", "support"]})
    return fsm


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


async def test_support_write_pushes_writing_screen(content, state):
    """SupportCallback(action='write') pushes support_writing and sets FSM state."""
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock()
    callback = MagicMock()
    callback.bot = bot
    callback.message = MagicMock(chat=MagicMock(id=42), message_id=999)
    callback.answer = AsyncMock()

    await handle_support_action(
        callback=callback,
        callback_data=SupportCallback(action="write"),
        state=state,
        content=content,
    )

    stack = await get_stack(state)
    assert "support_writing" in stack
    assert await state.get_state() == SupportState.writing_message.state
    bot.edit_message_text.assert_awaited_once()
    callback.answer.assert_awaited()


async def test_support_message_submission(content, state, session, current_user):
    """Submitting a non-empty message thanks the user and re-renders main menu."""
    await state.set_state(SupportState.writing_message)
    await state.update_data(
        {
            "root_message_id": 999,
            "nav_stack": ["main_menu", "support", "support_writing"],
        }
    )

    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1000))
    message = MagicMock()
    message.text = "Привет, мне нужна помощь."
    message.bot = bot
    message.chat = MagicMock(id=42)
    message.answer = AsyncMock()

    await handle_support_message(
        message=message,
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    # User received the "thanks" reply.
    message.answer.assert_awaited()
    # FSM state cleared.
    assert await state.get_state() is None
    # Main menu re-rendered (edit or send).
    assert (bot.edit_message_text.await_count + bot.send_message.await_count) >= 1


async def test_support_message_empty_text_asks_again(content, state, session, current_user):
    """Submitting blank/whitespace text keeps FSM state unchanged and prompts user again."""
    await state.set_state(SupportState.writing_message)

    bot = MagicMock()
    message = MagicMock()
    message.text = "   "
    message.bot = bot
    message.chat = MagicMock(id=42)
    message.answer = AsyncMock()

    await handle_support_message(
        message=message,
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    message.answer.assert_awaited_once()
    # State still in writing mode.
    assert await state.get_state() == SupportState.writing_message.state


async def test_support_message_long_text_is_truncated_in_preview(
    content, state, session, current_user
):
    """Long messages are accepted; preview truncation does not crash the handler."""
    await state.set_state(SupportState.writing_message)
    await state.update_data(
        {
            "root_message_id": 999,
            "nav_stack": ["main_menu", "support", "support_writing"],
        }
    )

    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1000))
    message = MagicMock()
    message.text = "X" * 500  # exceeds the 200-char preview limit
    message.bot = bot
    message.chat = MagicMock(id=42)
    message.answer = AsyncMock()

    await handle_support_message(
        message=message,
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    message.answer.assert_awaited()
    # Check truncation marker present in thanks reply.
    args, _ = message.answer.await_args
    assert "…" in args[0]
    assert await state.get_state() is None
