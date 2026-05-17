from collections.abc import Sequence
from math import ceil
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_ASSIGN_LIST_SCREEN_ID = "admin_assign_list"


class AdminAssignCallback(CallbackData, prefix="adm_assign"):
    action: Literal["pick", "unassign", "page"]
    lead_id: int
    admin_id: int = 0
    page: int = 1


def render_admin_assign_list(
    *,
    content: ContentService,
    lead_id: int,
    current_admin_id: int | None,
    admins: list[Any],
    page: int,
    total: int,
    page_size: int,
    stack: Sequence[str],
) -> Screen:
    total_pages = max(1, ceil(total / page_size))
    text = f"Кому назначить заявку?"
    extra = []
    if current_admin_id is not None:
        extra.append([InlineKeyboardButton(
            text="➖ Снять назначение",
            callback_data=AdminAssignCallback(
                action="unassign", lead_id=lead_id,
            ).pack(),
        )])
    for admin in admins:
        username = f"@{admin.username}" if admin.username else f"id{admin.id}"
        mark = "✓ " if current_admin_id == admin.id else ""
        extra.append([InlineKeyboardButton(
            text=f"{mark}{admin.first_name or ''} {username}".strip(),
            callback_data=AdminAssignCallback(
                action="pick", lead_id=lead_id, admin_id=admin.id,
            ).pack(),
        )])

    pagination_row = []
    if page > 1:
        pagination_row.append(InlineKeyboardButton(
            text="◀", callback_data=AdminAssignCallback(
                action="page", lead_id=lead_id, page=page - 1,
            ).pack(),
        ))
    pagination_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        pagination_row.append(InlineKeyboardButton(
            text="▶", callback_data=AdminAssignCallback(
                action="page", lead_id=lead_id, page=page + 1,
            ).pack(),
        ))
    if total_pages > 1:
        extra.append(pagination_row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=ADMIN_ASSIGN_LIST_SCREEN_ID, text=text, keyboard=keyboard)
