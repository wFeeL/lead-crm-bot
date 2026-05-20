from pathlib import Path

from app.bot.screens.support import (
    SUPPORT_SCREEN_ID,
    SUPPORT_WRITING_SCREEN_ID,
    SupportCallback,
    render_support,
    render_support_writing,
)
from app.bot.states.support import SupportState
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def test_render_support_shows_brand_contacts():
    content = _content()
    screen = render_support(content=content, stack=["main_menu", "support"])
    assert screen.screen_id == SUPPORT_SCREEN_ID
    assert content.brand.manager_username in screen.text
    assert content.brand.working_hours in screen.text


def test_render_support_has_write_button():
    screen = render_support(content=_content(), stack=["main_menu", "support"])
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("Написать" in lbl for lbl in labels)


def test_render_support_writing_has_nav_footer():
    """Writing screen exposes Back+Home so the user can bail out cleanly."""
    screen = render_support_writing(
        content=_content(), stack=["main_menu", "support", "support_writing"]
    )
    assert screen.screen_id == SUPPORT_WRITING_SCREEN_ID
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("Назад" in lbl for lbl in labels)
    assert any("Меню" in lbl for lbl in labels)


def test_render_support_writing_sets_next_state():
    screen = render_support_writing(
        content=_content(), stack=["main_menu", "support", "support_writing"]
    )
    assert screen.next_state == SupportState.writing_message


def test_support_callback_pack():
    assert SupportCallback(action="write").pack().startswith("support:")
