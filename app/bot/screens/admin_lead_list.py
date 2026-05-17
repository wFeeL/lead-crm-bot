from collections.abc import Sequence
from math import ceil
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_LEAD_LIST_SCREEN_ID = "admin_lead_list"


class AdminLeadListCallback(CallbackData, prefix="adm_list"):
    action: Literal["page", "open"]
    page: int = 1
    lead_id: int = 0


def render_admin_lead_list(
    *,
    content: ContentService,
    leads: list[Any],
    page: int,
    total: int,
    page_size: int,
    filter_label: str,
    stack: Sequence[str],
) -> Screen:
    total_pages = max(1, ceil(total / page_size))
    if total == 0:
        text = f"📋 {filter_label}\n\nНичего не найдено."
        keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
        return Screen(screen_id=ADMIN_LEAD_LIST_SCREEN_ID, text=text, keyboard=keyboard)

    text = f"📋 <b>{filter_label}</b> (всего {total}):"
    extra = []
    for lead in leads:
        status_emoji = (
            content.texts.statuses[lead.status].emoji
            if lead.status in content.texts.statuses
            else "•"
        )
        priority_emoji = (
            content.texts.priorities[lead.priority].emoji
            if lead.priority in content.texts.priorities
            else " "
        )
        cat = getattr(lead, "category", None)
        category_title = getattr(cat, "title", "?") if cat else "?"
        label = f"{priority_emoji} {status_emoji} №{lead.public_id} · {category_title}"
        extra.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=AdminLeadListCallback(
                        action="open", lead_id=lead.id, page=page
                    ).pack(),
                )
            ]
        )

    pagination_row = []
    if page > 1:
        pagination_row.append(
            InlineKeyboardButton(
                text="◀",
                callback_data=AdminLeadListCallback(action="page", page=page - 1).pack(),
            )
        )
    pagination_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(
                text="▶",
                callback_data=AdminLeadListCallback(action="page", page=page + 1).pack(),
            )
        )
    extra.append(pagination_row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=ADMIN_LEAD_LIST_SCREEN_ID, text=text, keyboard=keyboard)
