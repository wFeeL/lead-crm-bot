from collections.abc import Sequence
from math import ceil
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.handler import NOOP_CALLBACK
from app.bot.ui.screen import Screen
from app.services.content import ContentService

MY_LEADS_SCREEN_ID = "my_leads"
MY_LEAD_DETAIL_SCREEN_ID = "my_lead_detail"


class MyLeadsCallback(CallbackData, prefix="my_leads"):
    action: Literal["page", "open"]
    page: int = 1
    lead_id: int = 0


class MyLeadDetailCallback(CallbackData, prefix="my_lead"):
    action: Literal["cancel", "repeat"]
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
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data=NOOP_CALLBACK)
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


def _answer_label(answer: Any) -> str:
    """Prefer the question text shown to the client; fall back to the key."""
    question = getattr(answer, "question", None)
    question_text = getattr(question, "question_text", None) if question else None
    return question_text or getattr(answer, "key", "—")


def _file_display_name(file: Any, index: int) -> str:
    """Human label for a single attached file."""
    name = getattr(file, "file_name", None)
    if name:
        return name
    ftype = getattr(file, "file_type", None)
    if ftype == "photo":
        return f"Фото №{index + 1}"
    if ftype == "document":
        return f"Документ №{index + 1}"
    return f"Файл №{index + 1}"


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
    lines: list[str] = [
        f"<b>Заявка №{lead.public_id}</b>",
        f"{emoji} Статус: {status_label}",
        f"Категория: {category}",
    ]

    created_at = getattr(lead, "created_at", None)
    if created_at is not None:
        lines.append(f"Создана: {created_at.strftime('%Y-%m-%d %H:%M')}")

    # Show the full Q&A block so the client can see what they answered, not
    # just the concatenated description that looks like a wall of text.
    answers = list(getattr(lead, "answers", None) or [])
    if answers:
        lines.append("")
        lines.append("<b>Ваши ответы:</b>")
        for a in answers:
            value = getattr(a, "value_text", None) or "—"
            lines.append(f"• {_answer_label(a)}: {value}")

    # Attached files — show as a list so the user knows what they sent.
    files = list(getattr(lead, "files", None) or [])
    if files:
        lines.append("")
        lines.append(f"📎 <b>Прикреплённые файлы ({len(files)}):</b>")
        for i, f in enumerate(files):
            lines.append(f"• {_file_display_name(f, i)}")

    # Public comments (replies from the admin to the client). Internal comments
    # MUST NOT leak into the client view.
    comments = list(getattr(lead, "comments", None) or [])
    public_comments = [c for c in comments if not c.is_internal]
    if public_comments:
        lines.append("")
        lines.append("<b>Сообщения от менеджера:</b>")
        for c in sorted(public_comments, key=lambda x: getattr(x, "id", 0) or 0):
            lines.append(f"• {c.text}")

    if getattr(lead, "close_reason", None):
        lines.append("")
        lines.append(f"💬 Причина закрытия: {lead.close_reason}")

    text = "\n".join(lines)

    extra: list[list[InlineKeyboardButton]] = []
    if lead.status not in ("rejected", "cancelled"):
        extra.append(
            [
                InlineKeyboardButton(
                    text="🔁 Повторить",
                    callback_data=MyLeadDetailCallback(action="repeat", lead_id=lead.id).pack(),
                )
            ]
        )
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
