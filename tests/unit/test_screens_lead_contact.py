from pathlib import Path

from app.bot.screens.lead_contact import (
    LEAD_CONTACT_PROMPT_SCREEN_ID,
    make_contact_reply_keyboard,
    render_lead_contact_prompt,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def test_lead_contact_prompt_text():
    screen = render_lead_contact_prompt(
        content=_content(), stack=["main_menu", "lead_contact_prompt"]
    )
    assert screen.screen_id == LEAD_CONTACT_PROMPT_SCREEN_ID
    assert "Контакт" in screen.text


def test_make_contact_reply_keyboard_request_contact_button():
    kb = make_contact_reply_keyboard()
    btn = kb.keyboard[0][0]
    assert btn.request_contact is True
