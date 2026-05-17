from collections.abc import Sequence
from math import ceil
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

MY_LEADS_SCREEN_ID = "my_leads"
MY_LEAD_DETAIL_SCREEN_ID = "my_lead_detail"


class MyLeadsCallback(CallbackData, prefix="my_leads"):
    action: Literal["page", "open"]
    page: int = 1
    lead_id: int = 0


class MyLeadDetailCallback(CallbackData, prefix="my_lead"):
    action: Literal["open", "cancel"]
    lead_id: int


def _status_emoji_for(content: ContentService, status: str) -> str:
    statuses = content.texts.statuses
    if status in statuses:
        return statuses[status].emoji
    return "•"


def _format_lead_row(content: ContentService, lead: Any) -> str:
    emoji = _status_emoji_for(content, lead.status)
    category = getattr(lead.category, "title", "?") if getattr(lead, "category", None) else "?"
    return f"{emoji} №{lead.public_id} · {category}"


def render_my_leads(
    *,
    content: ContentService,
    leads: list[Any],
    page: int,
    total: int,
    stack: Sequence[str],
) -> Screen:
    page_size = content.config.ui.page_size_my_leads or 5
    total_pages = max(1, ceil(total / page_size))

    if total == 0:
        text = "📋 У вас пока нет заявок.\n\nОставьте первую — мы быстро ответим."
        keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
        return Screen(screen_id=MY_LEADS_SCREEN_ID, text=text, keyboard=keyboard)

    lead_rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=_format_lead_row(content, lead),
                callback_data=MyLeadsCallback(action="open", lead_id=lead.id).pack(),
            )
        ]
        for lead in leads
    ]

    pagination_row: list[InlineKeyboardButton] = []
    if page > 1:
        pagination_row.append(
            InlineKeyboardButton(
                text="◀",
                callback_data=MyLeadsCallback(action="page", page=page - 1).pack(),
            )
        )
    pagination_row.append(
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop")
    )
    if page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(
                text="▶",
                callback_data=MyLeadsCallback(action="page", page=page + 1).pack(),
            )
        )

    extra = lead_rows + [pagination_row]
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    text = f"📋 Ваши заявки (всего {total}):"
    return Screen(screen_id=MY_LEADS_SCREEN_ID, text=text, keyboard=keyboard)


def render_my_lead_detail(
    *,
    content: ContentService,
    lead: Any,
    stack: Sequence[str],
) -> Screen:
    emoji = _status_emoji_for(content, lead.status)
    status_label = (
        content.texts.statuses[lead.status].label
        if lead.status in content.texts.statuses
        else lead.status
    )
    category = getattr(lead.category, "title", "?") if getattr(lead, "category", None) else "?"
    text_lines = [
        f"<b>Заявка №{lead.public_id}</b>",
        f"{emoji} Статус: {status_label}",
        f"Категория: {category}",
        "",
    ]
    if getattr(lead, "description", None):
        text_lines.append(lead.description)
    text = "\n".join(text_lines)

    extra: list[list[InlineKeyboardButton]] = []
    if lead.status == "new":
        extra.append(
            [
                InlineKeyboardButton(
                    text="🚫 Отменить заявку",
                    callback_data=MyLeadDetailCallback(action="cancel", lead_id=lead.id).pack(),
                )
            ]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=MY_LEAD_DETAIL_SCREEN_ID, text=text, keyboard=keyboard)
