from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.bot.screens.admin_lead_list import (
    ADMIN_LEAD_LIST_SCREEN_ID,
    AdminLeadListCallback,
    render_admin_lead_list,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def _fake_lead(
    lead_id=1, public_id="TG-000001", status="new", priority="normal", category_title="Боты"
):
    return SimpleNamespace(
        id=lead_id,
        public_id=public_id,
        status=status,
        priority=priority,
        category=SimpleNamespace(title=category_title),
        created_at=datetime(2026, 5, 17, 10, 0, 0),
    )


def test_render_admin_lead_list_empty():
    screen = render_admin_lead_list(
        content=_content(),
        leads=[],
        page=1,
        total=0,
        page_size=5,
        filter_label="Новые",
        stack=["admin_menu"],
    )
    assert screen.screen_id == ADMIN_LEAD_LIST_SCREEN_ID
    assert "Ничего не найдено" in screen.text


def test_render_admin_lead_list_with_leads():
    leads = [_fake_lead(lead_id=i, public_id=f"TG-{i:06d}") for i in range(3)]
    screen = render_admin_lead_list(
        content=_content(),
        leads=leads,
        page=1,
        total=3,
        page_size=5,
        filter_label="🆕 Новые",
        stack=["admin_menu", "admin_lead_list"],
    )
    assert screen.screen_id == ADMIN_LEAD_LIST_SCREEN_ID
    assert "🆕 Новые" in screen.text
    assert "всего 3" in screen.text
    # Each lead should be a button with "open" action (format: adm_list:open:...)
    open_buttons = [
        btn
        for row in screen.keyboard.inline_keyboard
        for btn in row
        if btn.callback_data.startswith("adm_list:open:")
    ]
    assert len(open_buttons) == 3


def test_render_admin_lead_list_pagination():
    leads = [_fake_lead(lead_id=i, public_id=f"TG-{i:06d}") for i in range(5)]
    screen = render_admin_lead_list(
        content=_content(),
        leads=leads,
        page=2,
        total=15,
        page_size=5,
        filter_label="Все",
        stack=["admin_menu", "admin_lead_list"],
    )
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("◀" in lbl for lbl in labels)
    assert any("▶" in lbl for lbl in labels)
    assert any("2/3" in lbl for lbl in labels)


def test_admin_lead_list_callbacks_pack():
    assert AdminLeadListCallback(action="page", page=2).pack().startswith("adm_list:")
    assert AdminLeadListCallback(action="open", lead_id=42, page=1).pack().startswith("adm_list:")
