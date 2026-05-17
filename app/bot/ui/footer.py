from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton

from app.bot.ui.callbacks import NavCallback


def nav_footer(
    *,
    stack: Sequence[str],
    extra: Sequence[Sequence[InlineKeyboardButton]] | None = None,
) -> list[list[InlineKeyboardButton]]:
    """Build keyboard rows with the nav row at the bottom.

    Stack-aware:
    - len(stack) == 0: only Cancel (no prior screen, no root).
    - len(stack) == 1: Home + Cancel (already at root, no Back).
    - len(stack) >= 2: Back + Home + Cancel.
    """
    rows: list[list[InlineKeyboardButton]] = []
    if extra:
        rows.extend([list(row) for row in extra])

    nav_row: list[InlineKeyboardButton] = []
    if len(stack) >= 2:
        nav_row.append(
            InlineKeyboardButton(text="⬅ Назад", callback_data=NavCallback(action="back").pack())
        )
    if len(stack) >= 1:
        nav_row.append(
            InlineKeyboardButton(text="🏠 Меню", callback_data=NavCallback(action="home").pack())
        )
    nav_row.append(
        InlineKeyboardButton(text="🚫 Отмена", callback_data=NavCallback(action="cancel").pack())
    )
    rows.append(nav_row)
    return rows
