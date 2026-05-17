from dataclasses import dataclass

from aiogram.fsm.state import State
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup


@dataclass(frozen=True)
class Screen:
    """A renderable UI screen of the bot.

    Pure value object — produced by registry functions, consumed by render().
    """

    screen_id: str
    text: str
    keyboard: InlineKeyboardMarkup
    next_state: State | None = None
    reply_keyboard: ReplyKeyboardMarkup | None = None
