from collections.abc import Sequence
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

LEAD_EDIT_ANSWERS_SCREEN_ID = "lead_edit_answers"

_MAX_LINE_LEN = 60  # Telegram inline-button text is short — truncate aggressively.


class LeadEditAnswerCallback(CallbackData, prefix="lead_edit"):
    """Action on the edit-answers list screen.

    - ``pick``: open the i-th question for re-entry; other answers stay intact.
    - ``done``: return to the confirm screen with all current answers.
    """

    action: Literal["pick", "done"]
    index: int = 0


def _truncate(text: str, limit: int = _MAX_LINE_LEN) -> str:
    text = text.strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def render_lead_edit_answers(
    *,
    content: ContentService,
    draft: dict[str, Any],
    stack: Sequence[str],
) -> Screen:
    """List answers with a pencil button per row. The user only edits what they tap."""
    answers = list(draft.get("answers") or [])
    text_lines = [
        "✏ <b>Изменить ответы</b>",
        "",
        "Выберите вопрос, который хотите изменить. Остальные ответы останутся как есть.",
    ]

    extra: list[list[InlineKeyboardButton]] = []
    if not answers:
        text_lines.append("")
        text_lines.append("Нет ответов для редактирования.")
    else:
        for i, a in enumerate(answers):
            question_text = a.get("question_text") or a.get("key") or f"Вопрос {i + 1}"
            value = a.get("value_text") or "—"
            label = _truncate(f"{i + 1}. {question_text}: {value} ✏")
            extra.append(
                [
                    InlineKeyboardButton(
                        text=label,
                        callback_data=LeadEditAnswerCallback(action="pick", index=i).pack(),
                    )
                ]
            )

    extra.append(
        [
            InlineKeyboardButton(
                text="✅ Готово",
                callback_data=LeadEditAnswerCallback(action="done").pack(),
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(
        screen_id=LEAD_EDIT_ANSWERS_SCREEN_ID,
        text="\n".join(text_lines),
        keyboard=keyboard,
    )
