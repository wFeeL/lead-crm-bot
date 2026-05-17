from collections.abc import Sequence
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

LEAD_UPLOAD_FILES_SCREEN_ID = "lead_upload_files"


class LeadFilesCallback(CallbackData, prefix="lead_files"):
    action: Literal["continue", "delete_last", "back_to_questions"]


def render_lead_upload_files(
    *,
    content: ContentService,
    files: list[dict[str, Any]],
    max_files: int,
    stack: Sequence[str],
) -> Screen:
    lines = [f"📎 <b>Файлы</b> ({len(files)}/{max_files})"]
    if files:
        for f in files:
            name = f.get("file_name") or f.get("file_type") or "файл"
            lines.append(f"  • {name}")
    lines.append("")
    lines.append("Пришлите фото или документ — или нажмите «Продолжить».")
    text = "\n".join(lines)

    extra: list[list[InlineKeyboardButton]] = []
    extra.append(
        [
            InlineKeyboardButton(
                text="➡ Продолжить",
                callback_data=LeadFilesCallback(action="continue").pack(),
            )
        ]
    )
    if files:
        extra.append(
            [
                InlineKeyboardButton(
                    text="🗑 Удалить последний",
                    callback_data=LeadFilesCallback(action="delete_last").pack(),
                )
            ]
        )
    extra.append(
        [
            InlineKeyboardButton(
                text="⬅ К ответам",
                callback_data=LeadFilesCallback(action="back_to_questions").pack(),
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=LEAD_UPLOAD_FILES_SCREEN_ID, text=text, keyboard=keyboard)
