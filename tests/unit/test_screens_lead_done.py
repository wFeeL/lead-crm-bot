from pathlib import Path

from app.bot.screens.lead_done import LEAD_DONE_SCREEN_ID, render_lead_done
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def test_lead_done_includes_public_id_and_eta():
    content = _content()
    screen = render_lead_done(content=content, public_id="L123")
    assert screen.screen_id == LEAD_DONE_SCREEN_ID
    assert "L123" in screen.text
    assert str(content.brand.eta_response_hours) in screen.text


def test_lead_done_buttons():
    screen = render_lead_done(content=_content(), public_id="L1")
    labels = [b.text for row in screen.keyboard.inline_keyboard for b in row]
    assert any("Мои заявки" in lbl for lbl in labels)
    assert any("Меню" in lbl for lbl in labels)
