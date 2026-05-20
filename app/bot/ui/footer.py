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
    - len(stack) == 0: only Home (we have nothing else to offer).
    - len(stack) == 1: Home (already at root, no Back).
    - len(stack) >= 2: Back + Home.

    "Cancel" used to be a separate button here, but it was visually identical
    to Back for the user and confused testers ("Why two backs?"). We dropped it
    from the inline keyboard; ``/cancel`` typed as a command still clears the
    FSM and returns to MAIN_MENU via EscapeMiddleware, so the safety hatch
    isn't gone — just hidden from the visual UI.
    """
    rows: list[list[InlineKeyboardButton]] = []
    if extra:
        rows.extend([list(row) for row in extra])

    nav_row: list[InlineKeyboardButton] = []
    if len(stack) >= 2:
        nav_row.append(
            InlineKeyboardButton(text="⬅ Назад", callback_data=NavCallback(action="back").pack())
        )
    nav_row.append(
        InlineKeyboardButton(text="🏠 Меню", callback_data=NavCallback(action="home").pack())
    )
    rows.append(nav_row)
    return rows
