from pathlib import Path

from app.bot.screens.admin_menu import (
    ADMIN_MENU_SCREEN_ID,
    AdminMenuCallback,
    render_admin_menu,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def test_render_admin_menu_structure():
    screen = render_admin_menu(
        content=_content(),
        status_counts={"new": 3, "contacted": 1, "in_progress": 2, "waiting": 0},
        hot_count=2,
        company_name="TestCo",
    )
    assert screen.screen_id == ADMIN_MENU_SCREEN_ID
    assert "TestCo" in screen.text
    assert "Новые: 3" in screen.text
    assert "Связались: 1" in screen.text
    assert "В работе: 2" in screen.text
    assert "Ждут клиента: 0" in screen.text
    assert "Срочных и высоких: 2" in screen.text


def test_render_admin_menu_buttons_present():
    screen = render_admin_menu(
        content=_content(),
        status_counts={},
        hot_count=0,
        company_name="Co",
    )
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("Новые" in lbl for lbl in labels)
    assert any("Связались" in lbl for lbl in labels)
    assert any("В работе" in lbl for lbl in labels)
    assert any("Срочные" in lbl for lbl in labels)
    assert any("Все" in lbl for lbl in labels)
    assert any("CSV" in lbl for lbl in labels)
    assert any("Статистика" in lbl for lbl in labels)


def test_admin_menu_callbacks_pack():
    assert AdminMenuCallback(action="new").pack().startswith("adm_menu:")
    assert AdminMenuCallback(action="hot").pack().startswith("adm_menu:")
    assert AdminMenuCallback(action="csv").pack().startswith("adm_menu:")


def test_render_admin_menu_zero_counts():
    screen = render_admin_menu(
        content=_content(),
        status_counts={},
        hot_count=0,
        company_name="Company",
    )
    assert "Новые: 0" in screen.text
    assert "Срочных и высоких: 0" in screen.text
