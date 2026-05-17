from pathlib import Path

from app.bot.screens.lead_confirm import LEAD_CONFIRM_SCREEN_ID, LeadConfirmCallback, render_lead_confirm
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def test_confirm_text_includes_summary():
    draft = {
        "category_title": "Test Cat",
        "contact": "+7 999 000",
        "files": [{}, {}],
        "answers": [
            {"question_text": "Q1", "value_text": "A1"},
            {"question_text": "Q2", "value_text": ""},
        ],
    }
    screen = render_lead_confirm(content=_content(), draft=draft, stack=["main_menu", "lead_confirm"])
    assert screen.screen_id == LEAD_CONFIRM_SCREEN_ID
    assert "Test Cat" in screen.text
    assert "+7 999 000" in screen.text
    assert "2" in screen.text


def test_confirm_has_three_action_buttons():
    draft = {"category_title": "X", "answers": [], "files": [], "contact": "x"}
    screen = render_lead_confirm(content=_content(), draft=draft, stack=["main_menu", "lead_confirm"])
    labels = [b.text for row in screen.keyboard.inline_keyboard for b in row]
    assert any("Отправить" in lbl for lbl in labels)
    assert any("Изменить" in lbl for lbl in labels)
    assert any("Добавить файл" in lbl for lbl in labels)


def test_confirm_callbacks_pack():
    for a in ("submit", "edit_answers", "add_file"):
        assert LeadConfirmCallback(action=a).pack().startswith("lead_confirm:")
