"""Admin's '📎 Показать файлы' button delivers lead files as media groups."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.bot.screens.admin_lead_detail import AdminDetailCallback


def _file(file_id: str, file_type: str = "photo", name: str | None = None):
    return SimpleNamespace(
        telegram_file_id=file_id,
        file_type=file_type,
        file_name=name,
    )


def _lead(public_id="TG-000042", files=None):
    return SimpleNamespace(
        id=42,
        public_id=public_id,
        status="new",
        priority="normal",
        title="t",
        description="d",
        contact_name="C",
        contact_phone="+700",
        contact_username="u",
        category=SimpleNamespace(id=1, slug="other", title="Other"),
        assigned_admin_id=None,
        assigned_admin=None,
        user=SimpleNamespace(telegram_id=100, username="u", first_name="C"),
        created_at=datetime(2026, 5, 20, tzinfo=UTC),
        closed_at=None,
        close_reason=None,
        answers=[],
        files=files or [],
        comments=[],
    )


def test_show_files_callback_packs_with_action_value():
    """The screen emits the right callback that the router can dispatch."""
    cb = AdminDetailCallback(action="show_files", lead_id=42).pack()
    assert cb.startswith("adm_det:show_files:42")


def test_admin_lead_detail_shows_button_only_when_files_exist():
    """No '📎 Показать файлы' button when the lead has no attached files."""
    from pathlib import Path

    from app.bot.screens.admin_lead_detail import render_admin_lead_detail
    from app.services.content import ContentService

    content_dir = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"
    content = ContentService(ContentService.load(content_dir))

    no_files = _lead(files=[])
    screen_no = render_admin_lead_detail(
        content=content, lead=no_files, stack=["admin_menu", "admin_lead_list", "admin_lead_detail"]
    )
    callbacks = [btn.callback_data for row in screen_no.keyboard.inline_keyboard for btn in row]
    assert not any(cb.startswith("adm_det:show_files:") for cb in callbacks)

    with_files = _lead(files=[_file("AgADBAAD", "photo")])
    screen_yes = render_admin_lead_detail(
        content=content,
        lead=with_files,
        stack=["admin_menu", "admin_lead_list", "admin_lead_detail"],
    )
    callbacks = [btn.callback_data for row in screen_yes.keyboard.inline_keyboard for btn in row]
    assert any(cb.startswith("adm_det:show_files:42") for cb in callbacks)


@pytest.mark.asyncio
async def test_show_files_handler_sends_media_group(monkeypatch):
    """Tapping the button calls bot.send_media_group with the file ids."""
    from app.bot.routers.admin import menu as menu_router

    lead = _lead(
        files=[
            _file("photo_1", "photo"),
            _file("doc_1", "document", name="contract.pdf"),
            _file("photo_2", "photo"),
        ]
    )

    # Fake repo.
    class FakeRepo:
        def __init__(self, session):
            pass

        async def get(self, lid):
            return lead

    monkeypatch.setattr(menu_router, "LeadRepository", FakeRepo)
    monkeypatch.setattr(menu_router, "_is_admin_user", lambda *a, **kw: True)

    callback = MagicMock()
    callback.message = MagicMock()
    callback.message.chat.id = 999
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    callback.bot = MagicMock()
    callback.bot.send_media_group = AsyncMock()

    state = MagicMock()
    state.get_data = AsyncMock(return_value={})

    await menu_router.on_admin_detail_action(
        callback=callback,
        callback_data=AdminDetailCallback(action="show_files", lead_id=42),
        state=state,
        content=MagicMock(),
        session=MagicMock(),
        current_user=SimpleNamespace(id=1, telegram_id=1),
    )

    callback.bot.send_media_group.assert_awaited_once()
    media_arg = callback.bot.send_media_group.await_args.kwargs["media"]
    assert len(media_arg) == 3
    # All three file IDs sent.
    assert {m.media for m in media_arg} == {"photo_1", "doc_1", "photo_2"}
    # First item carries the caption with public_id.
    assert media_arg[0].caption is not None and "TG-000042" in media_arg[0].caption


@pytest.mark.asyncio
async def test_show_files_chunks_into_groups_of_10(monkeypatch):
    """15 files → 2 send_media_group calls (10 + 5)."""
    from app.bot.routers.admin import menu as menu_router

    lead = _lead(files=[_file(f"id_{i}", "photo") for i in range(15)])

    class FakeRepo:
        def __init__(self, session):
            pass

        async def get(self, lid):
            return lead

    monkeypatch.setattr(menu_router, "LeadRepository", FakeRepo)
    monkeypatch.setattr(menu_router, "_is_admin_user", lambda *a, **kw: True)

    callback = MagicMock()
    callback.message = MagicMock()
    callback.message.chat.id = 999
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    callback.bot = MagicMock()
    callback.bot.send_media_group = AsyncMock()

    state = MagicMock()
    state.get_data = AsyncMock(return_value={})

    await menu_router.on_admin_detail_action(
        callback=callback,
        callback_data=AdminDetailCallback(action="show_files", lead_id=42),
        state=state,
        content=MagicMock(),
        session=MagicMock(),
        current_user=SimpleNamespace(id=1, telegram_id=1),
    )

    assert callback.bot.send_media_group.await_count == 2
    chunk_sizes = [len(c.kwargs["media"]) for c in callback.bot.send_media_group.await_args_list]
    assert chunk_sizes == [10, 5]


@pytest.mark.asyncio
async def test_show_files_handler_no_files(monkeypatch):
    """When admin opens an old lead with no files, show alert instead of nothing."""
    from app.bot.routers.admin import menu as menu_router

    lead = _lead(files=[])

    class FakeRepo:
        def __init__(self, session):
            pass

        async def get(self, lid):
            return lead

    monkeypatch.setattr(menu_router, "LeadRepository", FakeRepo)
    monkeypatch.setattr(menu_router, "_is_admin_user", lambda *a, **kw: True)

    callback = MagicMock()
    callback.message = MagicMock()
    callback.message.chat.id = 999
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    callback.bot = MagicMock()
    callback.bot.send_media_group = AsyncMock()

    state = MagicMock()
    state.get_data = AsyncMock(return_value={})

    await menu_router.on_admin_detail_action(
        callback=callback,
        callback_data=AdminDetailCallback(action="show_files", lead_id=42),
        state=state,
        content=MagicMock(),
        session=MagicMock(),
        current_user=SimpleNamespace(id=1, telegram_id=1),
    )

    callback.bot.send_media_group.assert_not_called()
    callback.answer.assert_awaited()
    args, kwargs = callback.answer.call_args
    assert kwargs.get("show_alert") is True
