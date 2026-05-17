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
    question_id: int


def render_lead_question(
    *,
    content: ContentService,
    question: dict[str, Any],
    index: int,
    total: int,
    stack: Sequence[str],
) -> Screen:
    suffix = "" if question["required"] else "\n\n<i>Можно нажать «Пропустить».</i>"
    text = f"<b>Вопрос {index + 1}/{total}</b>\n\n{question['text']}{suffix}"

    extra: list[list[InlineKeyboardButton]] = []
    if question["type"] == QuestionType.CHOICE and question.get("options"):
        for i, option in enumerate(question["options"]):
            extra.append([
                InlineKeyboardButton(
                    text=option,
                    callback_data=LeadQuestionChoiceCallback(
                        question_id=question["id"], option_index=i
                    ).pack(),
                )
            ])
    action_row: list[InlineKeyboardButton] = []
    if not question["required"]:
        action_row.append(
            InlineKeyboardButton(
                text="↪ Пропустить",
                callback_data=LeadQuestionSkipCallback(question_id=question["id"]).pack(),
            )
        )
    if index > 0:
        action_row.append(
            InlineKeyboardButton(
                text="⬅ Предыдущий вопрос",
                callback_data=LeadQuestionBackCallback(question_id=question["id"]).pack(),
            )
        )
    if action_row:
        extra.append(action_row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=LEAD_QUESTION_SCREEN_ID, text=text, keyboard=keyboard)
