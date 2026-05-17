from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import Message

from app.bot.middlewares.escape import EscapeMiddleware


class _DummyState(StatesGroup):
    waiting = State()


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


def _message(text: str) -> Message:
    """Build a MagicMock that passes the isinstance(event, Message) check."""
    msg = MagicMock(spec=Message)
    msg.text = text
    return msg


async def test_escape_clears_fsm_on_slash_cancel(state: FSMContext):
    await state.set_state(_DummyState.waiting)
    handler = AsyncMock()
    msg = _message("/cancel")
    await EscapeMiddleware()(handler, msg, {"state": state})
    assert await state.get_state() is None
    handler.assert_not_awaited()


async def test_escape_clears_fsm_on_slash_menu(state: FSMContext):
    await state.set_state(_DummyState.waiting)
    handler = AsyncMock()
    msg = _message("/menu")
    await EscapeMiddleware()(handler, msg, {"state": state})
    assert await state.get_state() is None
    handler.assert_not_awaited()


async def test_escape_clears_fsm_on_slash_start_but_continues(state: FSMContext):
    await state.set_state(_DummyState.waiting)
    handler = AsyncMock()
    msg = _message("/start")
    await EscapeMiddleware()(handler, msg, {"state": state})
    assert await state.get_state() is None
    handler.assert_awaited_once()


async def test_escape_passthrough_for_normal_message(state: FSMContext):
    handler = AsyncMock()
    msg = _message("hello")
    await EscapeMiddleware()(handler, msg, {"state": state})
    handler.assert_awaited_once()


async def test_escape_passthrough_for_slash_cancel_without_fsm(state: FSMContext):
    """/cancel without active FSM still short-circuits (consistent behavior)."""
    handler = AsyncMock()
    msg = _message("/cancel")
    await EscapeMiddleware()(handler, msg, {"state": state})
    handler.assert_not_awaited()  # Still short-circuits per spec.


async def test_escape_passthrough_for_non_message_event(state: FSMContext):
    handler = AsyncMock()
    # CallbackQuery, for example — should pass through.
    cb = MagicMock()  # Not isinstance Message.
    await EscapeMiddleware()(handler, cb, {"state": state})
    handler.assert_awaited_once()
