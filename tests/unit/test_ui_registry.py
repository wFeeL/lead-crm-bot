import pytest
from aiogram.types import InlineKeyboardMarkup

from app.bot.ui.registry import SCREENS, get_renderer, register_screen
from app.bot.ui.screen import Screen


def _make_renderer(name: str):
    def renderer() -> Screen:
        return Screen(
            screen_id=name,
            text="x",
            keyboard=InlineKeyboardMarkup(inline_keyboard=[]),
        )
    return renderer


def test_register_and_get():
    renderer = _make_renderer("custom")
    register_screen("custom_t1", renderer)
    assert get_renderer("custom_t1") is renderer
    del SCREENS["custom_t1"]


def test_register_rejects_duplicate():
    renderer = _make_renderer("dup")
    register_screen("dup_t2", renderer)
    with pytest.raises(ValueError, match="already registered"):
        register_screen("dup_t2", renderer)
    del SCREENS["dup_t2"]


def test_get_renderer_missing_raises():
    with pytest.raises(KeyError, match="unknown_screen"):
        get_renderer("unknown_screen")
