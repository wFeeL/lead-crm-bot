from pathlib import Path

from app.bot.screens.admin_comment_prompt import (
    ADMIN_COMMENT_PROMPT_SCREEN_ID,
    render_admin_comment_prompt,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


STACK = ["admin_menu", "admin_lead_list", "admin_lead_detail", "admin_comment_prompt"]


def test_render_comment_prompt_internal():
    screen = render_admin_comment_prompt(
        content=_content(),
        lead_public_id="TG-000042",
        is_internal=True,
        stack=STACK,
    )
    assert screen.screen_id == ADMIN_COMMENT_PROMPT_SCREEN_ID
    assert "TG-000042" in screen.text
    assert "Внутренний" in screen.text


def test_render_comment_prompt_client_reply():
    screen = render_admin_comment_prompt(
        content=_content(),
        lead_public_id="TG-000099",
        is_internal=False,
        stack=STACK,
    )
    assert screen.screen_id == ADMIN_COMMENT_PROMPT_SCREEN_ID
    assert "TG-000099" in screen.text
    assert "клиенту" in screen.text.lower()


def test_render_comment_prompt_has_nav_footer():
    screen = render_admin_comment_prompt(
        content=_content(),
        lead_public_id="TG-000001",
        is_internal=True,
        stack=STACK,
    )
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("Назад" in lbl or "Меню" in lbl or "Отмена" in lbl for lbl in labels)
