from typing import Literal

from aiogram.filters.callback_data import CallbackData


class NavCallback(CallbackData, prefix="nav"):
    """Universal navigation callback (back/home/cancel)."""

    action: Literal["back", "home", "cancel"]
