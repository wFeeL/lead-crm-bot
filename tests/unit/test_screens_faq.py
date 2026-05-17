from pathlib import Path

import pytest

from app.bot.screens.faq import (
    FAQ_ANSWER_SCREEN_ID,
    FAQ_SCREEN_ID,
    FaqCallback,
    render_faq,
    render_faq_answer,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def test_render_faq_lists_questions():
    screen = render_faq(content=_content(), stack=["main_menu", "faq"])
    assert screen.screen_id == FAQ_SCREEN_ID
    faq_buttons = [
        btn for row in screen.keyboard.inline_keyboard
        for btn in row
        if "faq:" in btn.callback_data
    ]
    assert len(faq_buttons) == 5


def test_render_faq_answer_shows_specific_answer():
    content = _content()
    screen = render_faq_answer(content=content, index=0, stack=["main_menu", "faq", "faq_answer"])
    assert screen.screen_id == FAQ_ANSWER_SCREEN_ID
    assert content.faq[0].a in screen.text


def test_render_faq_answer_invalid_index_raises():
    with pytest.raises(IndexError):
        render_faq_answer(
            content=_content(), index=999, stack=["main_menu", "faq", "faq_answer"]
        )


def test_faq_callback_pack():
    cb = FaqCallback(index=0)
    assert cb.pack().startswith("faq:")
    assert FaqCallback.unpack(cb.pack()).index == 0
