from pathlib import Path

from app.bot.screens.admin_close_reason import (
    ADMIN_CLOSE_REASON_SCREEN_ID,
    AdminCloseReasonCallback,
    render_admin_close_reason,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


STACK = ["admin_menu", "admin_lead_list", "admin_lead_detail", "admin_close_reason"]


def test_render_close_reason_rejected():
    screen = render_admin_close_reason(
        content=_content(),
        lead_id=42,
        target_status="rejected",
        stack=STACK,
    )
    assert screen.screen_id == ADMIN_CLOSE_REASON_SCREEN_ID
    assert "отказа" in screen.text.lower()
    # Should NOT have a "skip" button for rejected
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert all("Без причины" not in lbl for lbl in labels)


def test_render_close_reason_done_has_skip():
    screen = render_admin_close_reason(
        content=_content(),
        lead_id=42,
        target_status="done",
        stack=STACK,
    )
    assert screen.screen_id == ADMIN_CLOSE_REASON_SCREEN_ID
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("Без причины" in lbl for lbl in labels)


def test_render_close_reason_buttons_have_correct_prefix():
    screen = render_admin_close_reason(
        content=_content(),
        lead_id=7,
        target_status="rejected",
        stack=STACK,
    )
    reason_buttons = [
        btn
        for row in screen.keyboard.inline_keyboard
        for btn in row
        if "adm_close:" in btn.callback_data
    ]
    assert len(reason_buttons) > 0


def test_admin_close_reason_callbacks_pack():
    prefix = "adm_close:"
    assert (
        AdminCloseReasonCallback(action="pick", lead_id=1, target_status="rejected", index=0)
        .pack()
        .startswith(prefix)
    )
    assert (
        AdminCloseReasonCallback(action="custom", lead_id=1, target_status="done", index=0)
        .pack()
        .startswith(prefix)
    )
    assert (
        AdminCloseReasonCallback(action="skip", lead_id=1, target_status="done")
        .pack()
        .startswith(prefix)
    )
