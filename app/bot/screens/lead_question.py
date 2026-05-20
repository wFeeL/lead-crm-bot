from collections.abc import Sequence
from typing import Any

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.core.constants import QuestionType
from app.services.content import ContentService

LEAD_QUESTION_SCREEN_ID = "lead_question"


class LeadQuestionChoiceCallback(CallbackData, prefix="lq_choice"):
    question_id: int
    option_index: int


class LeadQuestionSkipCallback(CallbackData, prefix="lq_skip"):
    question_id: int


class LeadQuestionBackCallback(CallbackData, prefix="lq_back"):
    """Navigate to the previous question (answers preserved)."""

    question_id: int


class LeadQuestionNextCallback(CallbackData, prefix="lq_next"):
    """Navigate forward to the next question. Refused if current is required-unanswered."""

    question_id: int


def _truncate(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def render_lead_question(
    *,
    content: ContentService,
    question: dict[str, Any],
    index: int,
    total: int,
    stack: Sequence[str],
    current_answer: str | None = None,
) -> Screen:
    """Render the question prompt.

    ``current_answer`` is the value previously entered for this question (when
    the user navigated back via ⬅/➡). It's shown above the prompt so the user
    sees what's on file before deciding whether to keep / overwrite it.
    """
    is_last = index == total - 1
    can_skip = not question["required"]
    has_answer = current_answer is not None and current_answer != ""

    text_lines = [
        f"<b>Вопрос {index + 1}/{total}</b>",
        "",
        question["text"],
    ]
    if has_answer:
        text_lines.append("")
        text_lines.append(f"<i>Ваш ответ:</i> {_truncate(current_answer)}")
        text_lines.append("<i>Можно ввести новый — он перезапишет старый.</i>")
    elif can_skip:
        text_lines.append("")
        text_lines.append("<i>Не обязательно — можно пропустить.</i>")
    text = "\n".join(text_lines)

    extra: list[list[InlineKeyboardButton]] = []

    # Choice options (one button per row for readability).
    if question["type"] == QuestionType.CHOICE and question.get("options"):
        for i, option in enumerate(question["options"]):
            extra.append(
                [
                    InlineKeyboardButton(
                        text=option,
                        callback_data=LeadQuestionChoiceCallback(
                            question_id=question["id"], option_index=i
                        ).pack(),
                    )
                ]
            )

    # Action row: ⬅ Previous | ↪ Skip (optional) | ➡ Next.
    #
    # "Next" is always present (so the user can scroll through already-answered
    # questions). For required questions without an answer, the handler refuses
    # navigation with a popup — the button doesn't disappear because that
    # would make the layout shift between questions and feel laggy.
    action_row: list[InlineKeyboardButton] = []
    if index > 0:
        action_row.append(
            InlineKeyboardButton(
                text="⬅ Предыдущий",
                callback_data=LeadQuestionBackCallback(question_id=question["id"]).pack(),
            )
        )
    if can_skip:
        skip_label = "↪ Пропустить и далее" if not has_answer else "↪ Очистить и далее"
        action_row.append(
            InlineKeyboardButton(
                text=skip_label,
                callback_data=LeadQuestionSkipCallback(question_id=question["id"]).pack(),
            )
        )
    next_label = "✅ К файлам ➡" if is_last else "Следующий ➡"
    action_row.append(
        InlineKeyboardButton(
            text=next_label,
            callback_data=LeadQuestionNextCallback(question_id=question["id"]).pack(),
        )
    )
    extra.append(action_row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=LEAD_QUESTION_SCREEN_ID, text=text, keyboard=keyboard)
