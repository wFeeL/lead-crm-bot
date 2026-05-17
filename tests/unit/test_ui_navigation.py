import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.ui.navigation import (
    get_root_message_id,
    get_stack,
    go_home,
    pop,
    push,
    set_root_message_id,
)


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


async def test_push_appends_screen_id(state: FSMContext):
    await push(state, "main_menu")
    await push(state, "faq")
    assert await get_stack(state) == ["main_menu", "faq"]


async def test_push_idempotent_for_same_top(state: FSMContext):
    await push(state, "main_menu")
    await push(state, "main_menu")
    assert await get_stack(state) == ["main_menu"]


async def test_pop_removes_top(state: FSMContext):
    await push(state, "main_menu")
    await push(state, "faq")
    popped = await pop(state)
    assert popped == "main_menu"
    assert await get_stack(state) == ["main_menu"]


async def test_pop_on_empty_returns_none(state: FSMContext):
    assert await pop(state) is None
    assert await get_stack(state) == []


async def test_pop_on_single_element_keeps_root(state: FSMContext):
    await push(state, "main_menu")
    popped = await pop(state)
    assert popped == "main_menu"
    assert await get_stack(state) == ["main_menu"]


async def test_go_home_resets_stack_to_main_menu(state: FSMContext):
    await push(state, "main_menu")
    await push(state, "faq")
    await push(state, "faq_answer")
    await go_home(state)
    assert await get_stack(state) == ["main_menu"]


async def test_root_message_id_setter_and_getter(state: FSMContext):
    assert await get_root_message_id(state) is None
    await set_root_message_id(state, 12345)
    assert await get_root_message_id(state) == 12345
