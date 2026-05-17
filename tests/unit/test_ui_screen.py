import dataclasses

import pytest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.screen import Screen


def test_screen_minimal_fields():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="OK", callback_data="ok")]])
    s = Screen(screen_id="main_menu", text="Hi", keyboard=keyboard)
    assert s.screen_id == "main_menu"
    assert s.text == "Hi"
    assert s.keyboard is keyboard
    assert s.reply_keyboard is None
    assert s.next_state is None


def test_screen_is_frozen():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    s = Screen(screen_id="x", text="y", keyboard=keyboard)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.text = "z"  # type: ignore[misc]


def test_screen_with_reply_keyboard():
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    inline = InlineKeyboardMarkup(inline_keyboard=[])
    reply = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Send")]])
    s = Screen(
        screen_id="contact_prompt",
        text="Send your phone",
        keyboard=inline,
        reply_keyboard=reply,
    )
    assert s.reply_keyboard is reply
