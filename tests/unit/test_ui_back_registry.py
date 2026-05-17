"""Tests for back_registry and back-navigation wiring in handle_nav."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.ui import back_registry
from app.bot.ui.back_registry import register_back, render_back
from app.bot.ui.callbacks import NavCallback
from app.bot.ui.handler import handle_nav
from app.bot.ui.navigation import get_stack, push, set_root_message_id


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


@pytest.fixture(autouse=True)
def _clear_back_registry():
    back_registry.clear()
    yield
    back_registry.clear()


async def test_render_back_calls_registered_renderer():
    seen: dict[str, object] = {}

    async def fake(*, bot, chat_id, state, session, content, current_user):
        seen["chat_id"] = chat_id

    register_back("my_leads", fake)
    ok = await render_back(
        "my_leads",
        bot=MagicMock(),
        chat_id=42,
        state=MagicMock(),
        session=MagicMock(),
        content=MagicMock(),
        current_user=MagicMock(),
    )
    assert ok is True
    assert seen["chat_id"] == 42


async def test_render_back_returns_false_for_unknown_screen():
    ok = await render_back(
        "totally_unknown",
        bot=MagicMock(),
        chat_id=42,
        state=MagicMock(),
        session=MagicMock(),
        content=MagicMock(),
        current_user=MagicMock(),
    )
    assert ok is False


async def test_handle_nav_back_invokes_registered_renderer(state: FSMContext):
    """Back from a known screen re-renders the new stack top."""
    await push(state, "main_menu")
    await push(state, "my_leads")
    await push(state, "my_lead_detail")
    await set_root_message_id(state, 100)

    rendered: dict[str, object] = {}

    async def fake_back(*, bot, chat_id, state, session, content, current_user):
        rendered["screen"] = "my_leads"
        rendered["chat_id"] = chat_id

    register_back("my_leads", fake_back)

    callback = AsyncMock()
    callback.message = MagicMock()
    callback.message.chat.id = 42
    callback.bot = MagicMock()

    await handle_nav(
        callback=callback,
        callback_data=NavCallback(action="back"),
        state=state,
        content=MagicMock(),
        current_user=SimpleNamespace(id=1),
        session=MagicMock(),
    )

    assert rendered == {"screen": "my_leads", "chat_id": 42}
    assert await get_stack(state) == ["main_menu", "my_leads"]
    callback.answer.assert_awaited_once()


async def test_handle_nav_back_falls_back_to_main_menu_when_unknown(state: FSMContext):
    """If no back-renderer is registered for the new top, collapse to MAIN_MENU."""
    await push(state, "main_menu")
    await push(state, "unknown_screen")
    await push(state, "child")

    main_menu_calls: dict[str, int] = {"count": 0}

    async def fake_main_menu(*, bot, chat_id, state, session, content, current_user):
        main_menu_calls["count"] += 1

    # We patch the lazy import used inside handle_nav's _render_main_menu.
    from app.bot.routers.user import menu as menu_module

    original = menu_module.render_and_show_main_menu

    async def patched(*, bot, chat_id, state, content, leads_count):
        main_menu_calls["count"] += 1

    menu_module.render_and_show_main_menu = patched
    try:
        callback = AsyncMock()
        callback.message = MagicMock()
        callback.message.chat.id = 42
        callback.bot = MagicMock()

        session = MagicMock()
        # Stub LeadRepository.count_by_user.
        from app.db.repositories import leads as leads_repo_module

        original_repo = leads_repo_module.LeadRepository

        class StubRepo:
            def __init__(self, _s):
                pass

            async def count_by_user(self, _uid):
                return 0

        leads_repo_module.LeadRepository = StubRepo
        try:
            await handle_nav(
                callback=callback,
                callback_data=NavCallback(action="back"),
                state=state,
                content=MagicMock(),
                current_user=SimpleNamespace(id=1),
                session=session,
            )
        finally:
            leads_repo_module.LeadRepository = original_repo
        assert main_menu_calls["count"] == 1
        callback.answer.assert_awaited_once()
    finally:
        menu_module.render_and_show_main_menu = original
