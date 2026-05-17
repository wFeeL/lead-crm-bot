from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.ui.callbacks import NavCallback
from app.bot.ui.handler import handle_nav
from app.bot.ui.navigation import get_stack, push, set_root_message_id


class _DummyState(StatesGroup):
    waiting = State()


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


async def test_handle_nav_back_pops_stack(state: FSMContext):
    await push(state, "main_menu")
    await push(state, "faq")
    callback = AsyncMock()
    await handle_nav(callback=callback, callback_data=NavCallback(action="back"), state=state)
    assert await get_stack(state) == ["main_menu"]
    callback.answer.assert_awaited_once()


async def test_handle_nav_home_resets_stack(state: FSMContext):
    await push(state, "main_menu")
    await push(state, "faq")
    await push(state, "faq_answer")
    callback = AsyncMock()
    await handle_nav(callback=callback, callback_data=NavCallback(action="home"), state=state)
    assert await get_stack(state) == ["main_menu"]
    callback.answer.assert_awaited_once()


async def test_handle_nav_cancel_clears_state_and_data(state: FSMContext):
    await state.set_state(_DummyState.waiting)
    await push(state, "main_menu")
    await push(state, "lead_question")
    await set_root_message_id(state, 555)
    callback = AsyncMock()
    await handle_nav(callback=callback, callback_data=NavCallback(action="cancel"), state=state)

    assert await state.get_state() is None
    data = await state.get_data()
    assert data == {}
    callback.answer.assert_awaited_once()


async def test_handle_nav_home_preserves_other_fsm_data(state: FSMContext):
    """home only clears nav_stack — draft data survives."""
    await state.update_data({"draft_lead": {"category_id": 1}})
    await push(state, "main_menu")
    await push(state, "lead_confirm")
    callback = AsyncMock()
    await handle_nav(callback=callback, callback_data=NavCallback(action="home"), state=state)

    data = await state.get_data()
    assert data.get("draft_lead") == {"category_id": 1}
    assert data.get("nav_stack") == ["main_menu"]
