from pathlib import Path
from types import SimpleNamespace

from app.bot.screens.admin_assign_list import (
    ADMIN_ASSIGN_LIST_SCREEN_ID,
    AdminAssignCallback,
    render_admin_assign_list,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def _fake_admin(admin_id=1, username="admin", first_name="Admin"):
    return SimpleNamespace(id=admin_id, username=username, first_name=first_name)


STACK = ["admin_menu", "admin_lead_list", "admin_lead_detail", "admin_assign_list"]


def test_render_assign_list_structure():
    admins = [_fake_admin(admin_id=i, username=f"admin{i}") for i in range(3)]
    screen = render_admin_assign_list(
        content=_content(),
        lead_id=42,
        current_admin_id=None,
        admins=admins,
        page=1,
        total=3,
        page_size=5,
        stack=STACK,
    )
    assert screen.screen_id == ADMIN_ASSIGN_LIST_SCREEN_ID
    assert "заявк" in screen.text.lower()


def test_render_assign_list_shows_admins():
    admins = [_fake_admin(admin_id=i, username=f"admin{i}", first_name=f"Admin{i}") for i in range(2)]
    screen = render_admin_assign_list(
        content=_content(),
        lead_id=10,
        current_admin_id=None,
        admins=admins,
        page=1,
        total=2,
        page_size=5,
        stack=STACK,
    )
    # format: adm_assign:pick:lead_id:admin_id:page
    pick_buttons = [
        btn
        for row in screen.keyboard.inline_keyboard
        for btn in row
        if btn.callback_data.startswith("adm_assign:pick:")
    ]
    assert len(pick_buttons) == 2


def test_render_assign_list_unassign_shown_when_assigned():
    admins = [_fake_admin(admin_id=1)]
    screen = render_admin_assign_list(
        content=_content(),
        lead_id=10,
        current_admin_id=1,
        admins=admins,
        page=1,
        total=1,
        page_size=5,
        stack=STACK,
    )
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("Снять" in lbl for lbl in labels)


def test_render_assign_list_no_unassign_when_unassigned():
    admins = [_fake_admin(admin_id=1)]
    screen = render_admin_assign_list(
        content=_content(),
        lead_id=10,
        current_admin_id=None,
        admins=admins,
        page=1,
        total=1,
        page_size=5,
        stack=STACK,
    )
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert all("Снять" not in lbl for lbl in labels)


def test_render_assign_list_marks_current_admin():
    admins = [_fake_admin(admin_id=1), _fake_admin(admin_id=2, username="other")]
    screen = render_admin_assign_list(
        content=_content(),
        lead_id=10,
        current_admin_id=1,
        admins=admins,
        page=1,
        total=2,
        page_size=5,
        stack=STACK,
    )
    pick_labels = [
        btn.text
        for row in screen.keyboard.inline_keyboard
        for btn in row
        if btn.callback_data.startswith("adm_assign:pick:")
    ]
    assert any("✓" in lbl for lbl in pick_labels)


def test_admin_assign_callbacks_pack():
    assert AdminAssignCallback(action="pick", lead_id=1, admin_id=2).pack().startswith("adm_assign:")
    assert AdminAssignCallback(action="unassign", lead_id=1).pack().startswith("adm_assign:")
    assert AdminAssignCallback(action="page", lead_id=1, page=2).pack().startswith("adm_assign:")
