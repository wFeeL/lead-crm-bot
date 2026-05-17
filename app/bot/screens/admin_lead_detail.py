from collections.abc import Sequence
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.core.constants import ALLOWED_STATUS_TRANSITIONS, LeadStatus
from app.services.content import ContentService

ADMIN_LEAD_DETAIL_SCREEN_ID = "admin_lead_detail"


class AdminDetailCallback(CallbackData, prefix="adm_det"):
    action: Literal["set_status", "set_priority", "comment_internal", "comment_reply", "assign", "assign_me"]
    lead_id: int
    value: str = ""  # For set_status / set_priority


def render_admin_lead_detail(
    *,
    content: ContentService,
    lead: Any,
    stack: Sequence[str],
) -> Screen:
    status_meta = content.texts.statuses.get(lead.status)
    priority_meta = content.texts.priorities.get(lead.priority)
    category_title = getattr(lead.category, "title", "?") if getattr(lead, "category", None) else "?"
    assigned_text = "—"
    if getattr(lead, "assigned_admin", None):
        admin = lead.assigned_admin
        username = f"@{admin.username}" if admin.username else f"id{admin.id}"
        assigned_text = f"{admin.first_name or ''} {username}".strip()

    lines = [
        f"<b>Заявка №{lead.public_id}</b> · {status_meta.emoji if status_meta else ''} {status_meta.label if status_meta else lead.status} · "
        f"{priority_meta.emoji if priority_meta else ''} {priority_meta.label if priority_meta else lead.priority}",
        f"Категория: {category_title}",
        f"Контакт: {lead.contact_phone or lead.contact_username or '—'}",
        f"Назначен: {assigned_text}",
        f"Создана: {lead.created_at.isoformat(timespec='minutes')}",
        "",
        lead.description or "",
    ]
    if lead.close_reason:
        lines.append(f"\n💬 Причина закрытия: {lead.close_reason}")
    text = "\n".join(lines)

    # Status buttons (dynamic per available transitions)
    available = ALLOWED_STATUS_TRANSITIONS.get(LeadStatus(lead.status), set())
    status_row = []
    for target in (LeadStatus.CONTACTED, LeadStatus.IN_PROGRESS, LeadStatus.WAITING):
        if target in available:
            meta = content.texts.statuses.get(target.value)
            status_row.append(InlineKeyboardButton(
                text=f"{meta.emoji if meta else ''} {meta.label if meta else target.value}",
                callback_data=AdminDetailCallback(
                    action="set_status", lead_id=lead.id, value=target.value
                ).pack(),
            ))
    close_row = []
    for target in (LeadStatus.DONE, LeadStatus.REJECTED):
        if target in available:
            meta = content.texts.statuses.get(target.value)
            close_row.append(InlineKeyboardButton(
                text=f"{meta.emoji if meta else ''} {meta.label if meta else target.value}",
                callback_data=AdminDetailCallback(
                    action="set_status", lead_id=lead.id, value=target.value
                ).pack(),
            ))

    # Priority row (always 4 buttons; current marked).
    prio_row = []
    for p in ("low", "normal", "high", "urgent"):
        meta = content.texts.priorities.get(p)
        mark = "✓ " if lead.priority == p else ""
        prio_row.append(InlineKeyboardButton(
            text=f"{mark}{meta.emoji if meta else ''}",
            callback_data=AdminDetailCallback(
                action="set_priority", lead_id=lead.id, value=p
            ).pack(),
        ))

    # Comments + assignment row.
    actions_row1 = [
        InlineKeyboardButton(
            text="📝 Внутренний",
            callback_data=AdminDetailCallback(
                action="comment_internal", lead_id=lead.id
            ).pack(),
        ),
        InlineKeyboardButton(
            text="💬 Клиенту",
            callback_data=AdminDetailCallback(
                action="comment_reply", lead_id=lead.id
            ).pack(),
        ),
    ]
    actions_row2 = [
        InlineKeyboardButton(
            text="👤 Назначить...",
            callback_data=AdminDetailCallback(action="assign", lead_id=lead.id).pack(),
        ),
    ]
    if not getattr(lead, "assigned_admin_id", None):
        actions_row2.insert(0, InlineKeyboardButton(
            text="🙋 Взять себе",
            callback_data=AdminDetailCallback(action="assign_me", lead_id=lead.id).pack(),
        ))

    extra = []
    if status_row:
        extra.append(status_row)
    if close_row:
        extra.append(close_row)
    extra.append(prio_row)
    extra.append(actions_row1)
    extra.append(actions_row2)

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=ADMIN_LEAD_DETAIL_SCREEN_ID, text=text, keyboard=keyboard)
