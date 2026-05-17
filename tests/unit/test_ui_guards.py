from unittest.mock import AsyncMock, MagicMock

from app.bot.ui.guards import is_root_message


async def test_is_root_message_true_when_match():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.message_id = 123
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"root_message_id": 123})
    assert await is_root_message(cb, state) is True


async def test_is_root_message_false_when_stale():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.message_id = 999
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"root_message_id": 123})
    assert await is_root_message(cb, state) is False


async def test_is_root_message_false_when_no_root_yet():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.message_id = 123
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    assert await is_root_message(cb, state) is False


async def test_is_root_message_false_when_no_message():
    cb = MagicMock()
    cb.message = None
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"root_message_id": 123})
    assert await is_root_message(cb, state) is False
