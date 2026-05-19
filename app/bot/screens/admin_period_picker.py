"""Period picker for the admin lead list.

Periods are stored as a short string (``"today"``, ``"yesterday"``, ``"week"``,
``"month"``, ``"all"``) in FSM ``admin_filter.period``. The repository converts
them to a concrete ``(date_from, date_to)`` range at query time so the picker
stays UI-only — no datetime serialization in FSM.
"""

from collections.abc import Sequence
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen

ADMIN_PERIOD_PICKER_SCREEN_ID = "admin_period_picker"

# Stable string keys; order matters for the picker layout.
PeriodKey = Literal["today", "yesterday", "week", "month", "all"]
PERIOD_LABELS: dict[str, str] = {
    "today": "Сегодня",
    "yesterday": "Вчера",
    "week": "Последние 7 дней",
    "month": "Последние 30 дней",
    "all": "Все время",
}


class AdminPeriodCallback(CallbackData, prefix="adm_per"):
    period: str  # one of PERIOD_LABELS keys


def render_admin_period_picker(
    *,
    current_period: str | None,
    stack: Sequence[str],
) -> Screen:
    rows: list[list[InlineKeyboardButton]] = []
    # Two columns for the four time presets, "Все время" full-width below.
    short = ["today", "yesterday", "week", "month"]
    for left, right in (short[0:2], short[2:4]):
        rows.append(
            [
                InlineKeyboardButton(
                    text=("✓ " if current_period == left else "") + PERIOD_LABELS[left],
                    callback_data=AdminPeriodCallback(period=left).pack(),
                ),
                InlineKeyboardButton(
                    text=("✓ " if current_period == right else "") + PERIOD_LABELS[right],
                    callback_data=AdminPeriodCallback(period=right).pack(),
                ),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=("✓ " if current_period in (None, "all") else "") + PERIOD_LABELS["all"],
                callback_data=AdminPeriodCallback(period="all").pack(),
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=rows))
    text = (
        "📅 <b>Период</b>\n\n"
        "Выберите интервал — он будет применён к открываемому далее списку заявок."
    )
    return Screen(screen_id=ADMIN_PERIOD_PICKER_SCREEN_ID, text=text, keyboard=keyboard)
