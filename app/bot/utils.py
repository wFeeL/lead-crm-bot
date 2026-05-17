from typing import Any

from aiogram.exceptions import TelegramBadRequest


async def remove_inline_keyboard(message: Any) -> None:
    if message is None or not hasattr(message, "edit_reply_markup"):
        return
    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        return


async def replace_message_text(message: Any, text: str, *, reply_markup: Any = None) -> None:
    if message is None or not hasattr(message, "edit_text"):
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        if hasattr(message, "answer"):
            await message.answer(text, reply_markup=reply_markup)
