from pathlib import Path

from app.bot.screens.main_menu import MAIN_MENU_SCREEN_ID, MainMenuCallback, render_main_menu
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def test_main_menu_renders_buttons():
    screen = render_main_menu(content=_content(), leads_count=0)
    assert screen.screen_id == MAIN_MENU_SCREEN_ID
    assert "Выберите действие" in screen.text
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("Оставить заявку" in lbl for lbl in labels)
    assert any("Мои заявки" in lbl for lbl in labels)
    assert any("Менеджер" in lbl for lbl in labels)
    assert any("FAQ" in lbl for lbl in labels)


def test_main_menu_callbacks_pack():
    assert MainMenuCallback(action="create_lead").pack().startswith("menu:")


def test_main_menu_includes_leads_count_in_label():
    screen = render_main_menu(content=_content(), leads_count=3)
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    my_leads_label = next(lbl for lbl in labels if "Мои заявки" in lbl)
    assert "3" in my_leads_label


def test_main_menu_omits_count_when_zero():
    screen = render_main_menu(content=_content(), leads_count=0)
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    my_leads_label = next(lbl for lbl in labels if "Мои заявки" in lbl)
    assert "(" not in my_leads_label
