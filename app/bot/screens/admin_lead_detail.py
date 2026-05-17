from collections.abc import Sequence
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.core.constants import ALLOWED_STATUS_TRANSITIONS, LeadStatus
from app.services.content import ContentService

ADMIN_LEAD_DETAIL_SCREEN_ID = "admin_lead_detail"

_PRIORITY_BUTTON_LABELS = {
    "low": "Низкий",
    "normal": "Обычный",
    "high": "Высокий",
    "urgent": "Срочно",
}


class AdminDetailCallback(CallbackData, prefix="adm_det"):
    action: Literal[
        "set_status",
        "set_priority",
        "comment_internal",
        "comment_reply",
        "assign",
        "assign_me",
    ]
    lead_id: int
    value: str = ""  # For set_status / set_priority


def _answer_label(answer: Any) -> str:
    question = getattr(answer, "question", None)
    question_text = getattr(question, "question_text", None) if question else None
    return question_text or getattr(answer, "key", "—")


def _admin_label(admin: Any) -> str:
    if admin is None:
        return "—"
    name = (getattr(admin, "first_name", None) or "").strip()
    username = f"@{admin.username}" if getattr(admin, "username", None) else ""
    if name and username:
        return f"{name} {username}"
    return name or username or f"#{getattr(admin, 'id', '?')}"


def render_admin_lead_detail(
    *,
    content: ContentService,
    lead: Any,
    stack: Sequence[str],
) -> Screen:
    status_meta = content.texts.statuses.get(lead.status)
    priority_meta = content.texts.priorities.get(lead.priority)
    cat = getattr(lead, "category", None)
    category_title = getattr(cat, "title", "?") if cat else "?"
    assigned_text = "—"
    if getattr(lead, "assigned_admin", None):
        admin = lead.assigned_admin
        username = f"@{admin.username}" if admin.username else f"id{admin.id}"
        assigned_text = f"{admin.first_name or ''} {username}".strip()

    s_emoji = status_meta.emoji if status_meta else ""
    s_label = status_meta.label if status_meta else lead.status
    p_emoji = priority_meta.emoji if priority_meta else ""
    p_label = priority_meta.label if priority_meta else lead.priority

    user = getattr(lead, "user", None)
    client_parts: list[str] = []
    if user is not None:
        if getattr(user, "first_name", None):
            client_parts.append(user.first_name)
        if getattr(user, "username", None):
            client_parts.append(f"@{user.username}")
    client_text = " / ".join(client_parts) or "—"
    contact_text = lead.contact_phone or lead.contact_username or "—"

    lines = [
        f"<b>Заявка №{lead.public_id}</b>",
        f"Статус: {s_emoji} {s_label}",
        f"Приоритет: {p_emoji} {p_label}",
        f"Категория: {category_title}",
        f"Клиент: {client_text}",
        f"Контакт: {contact_text}",
        f"Назначен: {assigned_text}",
        f"Создана: {lead.created_at.strftime('%Y-%m-%d %H:%M')}",
    ]

    # Full Q&A block — show the human question text, not the English key.
    answers = list(getattr(lead, "answers", None) or [])
    if answers:
        lines.append("")
        lines.append("<b>Ответы клиента:</b>")
        for answer in answers:
            value = (
                getattr(answer, "value_text", None) or getattr(answer, "value_json", None) or "—"
            )
            lines.append(f"• {_answer_label(answer)}: {value}")

    # Files counter (useful for admin triage).
    files = list(getattr(lead, "files", None) or [])
    if files:
        lines.append("")
        lines.append(f"📎 Файлов: {len(files)}")

    # Internal admin comments stay visible to admins.
    comments = list(getattr(lead, "comments", None) or [])
    if comments:
        lines.append("")
        lines.append("<b>Комментарии:</b>")
        for c in sorted(comments, key=lambda x: getattr(x, "id", 0) or 0):
            visibility = "внутренний" if c.is_internal else "клиенту"
            author = _admin_label(getattr(c, "admin", None))
            lines.append(f"• {author} ({visibility}): {c.text}")

    if lead.close_reason:
        lines.append("")
        lines.append(f"💬 Причина закрытия: {lead.close_reason}")

    text = "\n".join(lines)

    extra: list[list[InlineKeyboardButton]] = []

    # --- Status transitions: split into "active flow" and "close" rows. ---
    available = ALLOWED_STATUS_TRANSITIONS.get(LeadStatus(lead.status), set())
    status_row: list[InlineKeyboardButton] = []
    for target in (LeadStatus.CONTACTED, LeadStatus.IN_PROGRESS, LeadStatus.WAITING):
        if target in available:
            meta = content.texts.statuses.get(target.value)
            label = f"{meta.emoji if meta else ''} {meta.label if meta else target.value}".strip()
            status_row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=AdminDetailCallback(
                        action="set_status", lead_id=lead.id, value=target.value
                    ).pack(),
                )
            )
    close_row: list[InlineKeyboardButton] = []
    for target in (LeadStatus.DONE, LeadStatus.REJECTED):
        if target in available:
            meta = content.texts.statuses.get(target.value)
            label = f"{meta.emoji if meta else ''} {meta.label if meta else target.value}".strip()
            close_row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=AdminDetailCallback(
                        action="set_status", lead_id=lead.id, value=target.value
                    ).pack(),
                )
            )
    if status_row:
        extra.append(status_row)
    if close_row:
        extra.append(close_row)

    # --- Priority row: labeled buttons, current marked with ✓. ---
    prio_row: list[InlineKeyboardButton] = []
    for p in ("low", "normal", "high", "urgent"):
        meta = content.texts.priorities.get(p)
        emoji = meta.emoji if meta else ""
        mark = "✓ " if lead.priority == p else ""
        prio_row.append(
            InlineKeyboardButton(
                text=f"{mark}{emoji} {_PRIORITY_BUTTON_LABELS[p]}".strip(),
                callback_data=AdminDetailCallback(
                    action="set_priority", lead_id=lead.id, value=p
                ).pack(),
            )
        )
    # Telegram caps inline-button width — split priorities into two rows of two
    # for a tidy 2×2 grid below the status rows.
    extra.append(prio_row[:2])
    extra.append(prio_row[2:])

    # --- Comments row: internal + reply-to-client side by side. ---
    extra.append(
        [
            InlineKeyboardButton(
                text="📝 Внутренний комментарий",
                callback_data=AdminDetailCallback(
                    action="comment_internal", lead_id=lead.id
                ).pack(),
            ),
            InlineKeyboardButton(
                text="💬 Ответить клиенту",
                callback_data=AdminDetailCallback(action="comment_reply", lead_id=lead.id).pack(),
            ),
        ]
    )

    # --- Assignment row: "Take" + "Assign…" only shown when relevant. ---
    assignment_row: list[InlineKeyboardButton] = []
    if not getattr(lead, "assigned_admin_id", None):
        assignment_row.append(
            InlineKeyboardButton(
                text="🙋 Взять себе",
                callback_data=AdminDetailCallback(action="assign_me", lead_id=lead.id).pack(),
            )
        )
    assignment_row.append(
        InlineKeyboardButton(
            text="👤 Назначить…",
            callback_data=AdminDetailCallback(action="assign", lead_id=lead.id).pack(),
        )
    )
    extra.append(assignment_row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=ADMIN_LEAD_DETAIL_SCREEN_ID, text=text, keyboard=keyboard)
