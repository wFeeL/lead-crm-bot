from collections.abc import Sequence
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

LEAD_CONFIRM_SCREEN_ID = "lead_confirm"


class LeadConfirmCallback(CallbackData, prefix="lead_confirm"):
    action: Literal["submit", "edit_answers", "add_file"]


def render_lead_confirm(
    *,
    content: ContentService,
    draft: dict[str, Any],
    stack: Sequence[str],
) -> Screen:
    answers = draft.get("answers", [])
    lines = [
        "<b>✅ Проверьте заявку</b>",
        "",
        f"Категория: {draft.get('category_title', '?')}",
        f"Контакт: {draft.get('contact') or '—'}",
        f"Файлов: {len(draft.get('files', []))}",
        "",
        "<b>Ответы:</b>",
    ]
    for a in answers:
        q = a.get("question_text", "—")
        v = a.get("value_text") or "—"
        lines.append(f"  • {q}: {v}")
    text = "\n".join(lines)

    extra = [
        [
            InlineKeyboardButton(
                text="✅ Отправить",
                callback_data=LeadConfirmCallback(action="submit").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="✏ Изменить ответы",
                callback_data=LeadConfirmCallback(action="edit_answers").pack(),
            ),
            InlineKeyboardButton(
                text="➕ Добавить файл",
                callback_data=LeadConfirmCallback(action="add_file").pack(),
            ),
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=LEAD_CONFIRM_SCREEN_ID, text=text, keyboard=keyboard)
