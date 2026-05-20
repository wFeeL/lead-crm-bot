"""Media-album debounce: many files in a burst → one render at the end."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.routers.user.lead_create import (
    _pending_file_renders,
    _schedule_files_render,
)


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    s = FSMContext(storage=storage, key=key)
    await s.update_data(files=[])
    return s


@pytest.fixture
def fake_content():
    return SimpleNamespace(
        config=SimpleNamespace(ui=SimpleNamespace(page_size_admin=5, page_size_my_leads=5)),
    )


@pytest.fixture(autouse=True)
async def cleanup_tasks():
    yield
    # Cancel any pending debounce tasks left over from a test.
    for task in list(_pending_file_renders.values()):
        task.cancel()
    _pending_file_renders.clear()


async def test_rapid_schedules_only_render_once(monkeypatch, state, fake_content):
    """6 files in <1s should produce exactly ONE render call (last one)."""
    calls = []

    async def fake_render(*, bot, chat_id, state, content):
        calls.append((chat_id, len((await state.get_data()).get("files", []))))

    monkeypatch.setattr("app.bot.routers.user.lead_create._render_files_screen_now", fake_render)

    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.delete_message = AsyncMock()

    # Simulate 6 album files arriving rapidly.
    for _ in range(6):
        files = (await state.get_data()).get("files", [])
        files.append({"telegram_file_id": "x", "file_type": "photo"})
        await state.update_data(files=files)
        _schedule_files_render(bot=bot, chat_id=42, state=state, content=fake_content)
        await asyncio.sleep(0.05)  # well under debounce window

    # Wait for the debounce window to elapse + a bit.
    await asyncio.sleep(1.0)

    # Exactly one render — for the last batch state.
    assert len(calls) == 1
    assert calls[0] == (42, 6)


async def test_single_file_renders_after_delay(monkeypatch, state, fake_content):
    """A single file (not part of an album) still renders, just after the delay."""
    rendered = asyncio.Event()
    captured = {}

    async def fake_render(*, bot, chat_id, state, content):
        captured["chat_id"] = chat_id
        rendered.set()

    monkeypatch.setattr("app.bot.routers.user.lead_create._render_files_screen_now", fake_render)

    files = [{"telegram_file_id": "x", "file_type": "photo"}]
    await state.update_data(files=files)
    _schedule_files_render(bot=MagicMock(), chat_id=42, state=state, content=fake_content)

    await asyncio.wait_for(rendered.wait(), timeout=2.0)
    assert captured["chat_id"] == 42
