from pathlib import Path
from types import SimpleNamespace

from app.bot.screens.lead_category import (
    LEAD_CATEGORY_SCREEN_ID,
    LeadCategoryCallback,
    render_lead_category,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def _cat(slug, title):
    return SimpleNamespace(slug=slug, title=title)


def test_lead_category_empty():
    screen = render_lead_category(
        content=_content(), categories=[], stack=["main_menu", "lead_category"]
    )
    assert screen.screen_id == LEAD_CATEGORY_SCREEN_ID
    assert "Категории" in screen.text


def test_lead_category_with_items_has_button_per_category():
    cats = [_cat("a", "Cat A"), _cat("b", "Cat B")]
    screen = render_lead_category(
        content=_content(), categories=cats, stack=["main_menu", "lead_category"]
    )
    btns = [
        b for row in screen.keyboard.inline_keyboard for b in row if "lead_cat:" in b.callback_data
    ]
    assert len(btns) == 2
    assert {b.text for b in btns} == {"Cat A", "Cat B"}


def test_lead_category_callback_pack():
    assert LeadCategoryCallback(slug="x").pack().startswith("lead_cat:")
