from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.bot.screens.my_leads import (
    MY_LEAD_DETAIL_SCREEN_ID,
    MY_LEADS_SCREEN_ID,
    MyLeadDetailCallback,
    MyLeadsCallback,
    render_my_lead_detail,
    render_my_leads,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def _fake_lead(lead_id=1, public_id="ABC100", status="new", category_title="Боты"):
    return SimpleNamespace(
        id=lead_id,
        public_id=public_id,
        status=status,
        title=category_title,
        description="Описание заявки",
        category=SimpleNamespace(title=category_title),
        created_at=datetime(2026, 5, 17, 10, 0, 0),
        answers=[],
        files=[],
        user_id=42,
    )


def test_render_my_leads_empty_state():
    screen = render_my_leads(
        content=_content(), leads=[], page=1, total=0, stack=["main_menu", "my_leads"]
    )
    assert screen.screen_id == MY_LEADS_SCREEN_ID
    assert "нет заявок" in screen.text.lower()


def test_render_my_leads_lists_leads_with_buttons():
    leads = [_fake_lead(lead_id=i, public_id=f"L{i}") for i in range(3)]
    screen = render_my_leads(
        content=_content(), leads=leads, page=1, total=3, stack=["main_menu", "my_leads"]
    )
    lead_buttons = [
        btn for row in screen.keyboard.inline_keyboard
        for btn in row if "my_leads:" in btn.callback_data
    ]
    assert len(lead_buttons) == 3


def test_render_my_leads_pagination_buttons():
    leads = [_fake_lead(lead_id=i, public_id=f"L{i}") for i in range(5)]
    screen = render_my_leads(
        content=_content(), leads=leads, page=2, total=15, stack=["main_menu", "my_leads"]
    )
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    # page=2, total=15 with page_size=5 → 3 pages → has both ◀ and ▶
    assert any("◀" in lbl for lbl in labels)
    assert any("▶" in lbl for lbl in labels)
    assert any("2/3" in lbl for lbl in labels)


def test_render_my_leads_no_prev_on_page_1():
    leads = [_fake_lead(lead_id=i, public_id=f"L{i}") for i in range(5)]
    screen = render_my_leads(
        content=_content(), leads=leads, page=1, total=15, stack=["main_menu", "my_leads"]
    )
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert all("◀" not in lbl for lbl in labels)
    assert any("▶" in lbl for lbl in labels)


def test_render_my_lead_detail_shows_info():
    lead = _fake_lead(public_id="L42")
    screen = render_my_lead_detail(
        content=_content(), lead=lead, stack=["main_menu", "my_leads", "my_lead_detail"]
    )
    assert screen.screen_id == MY_LEAD_DETAIL_SCREEN_ID
    assert "L42" in screen.text


def test_my_lead_detail_cancel_button_for_new():
    lead = _fake_lead(public_id="L1", status="new")
    screen = render_my_lead_detail(
        content=_content(), lead=lead, stack=["main_menu", "my_leads", "my_lead_detail"]
    )
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("Отменить" in lbl for lbl in labels)


def test_my_lead_detail_no_cancel_button_for_done():
    lead = _fake_lead(public_id="L1", status="done")
    screen = render_my_lead_detail(
        content=_content(), lead=lead, stack=["main_menu", "my_leads", "my_lead_detail"]
    )
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert all("Отменить" not in lbl for lbl in labels)


def test_my_leads_callbacks_pack():
    assert MyLeadsCallback(action="page", page=2).pack().startswith("my_leads:")
    assert MyLeadDetailCallback(action="cancel", lead_id=42).pack().startswith("my_lead:")
