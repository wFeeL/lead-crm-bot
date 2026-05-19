"""Read-only audit log for a single lead.

Renders every ``LeadEvent`` chronologically with actor name + human label.
Reused by admin's «📜 История» action on the lead detail screen.
"""

from collections.abc import Sequence
from typing import Any

from aiogram.types import InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.core.constants import LeadEventType
from app.services.content import ContentService

ADMIN_LEAD_TIMELINE_SCREEN_ID = "admin_lead_timeline"

_EVENT_VERBS: dict[str, str] = {
    LeadEventType.LEAD_CREATED: "🆕 заявка создана",
    LeadEventType.STATUS_CHANGED: "🔄 статус",
    LeadEventType.ADMIN_ASSIGNED: "👤 назначен исполнитель",
    LeadEventType.COMMENT_ADDED: "📝 комментарий",
    LeadEventType.FILE_UPLOADED: "📎 файл",
    LeadEventType.CLIENT_CANCELLED: "🚫 отмена клиентом",
    LeadEventType.LEAD_DELETED: "🗑 удалена",
}


def _actor_label(event: Any) -> str:
    actor = getattr(event, "actor", None)
    if actor is None:
        return "система"
    name = (getattr(actor, "first_name", None) or "").strip()
    username = f"@{actor.username}" if getattr(actor, "username", None) else ""
    if name and username:
        return f"{name} {username}"
    return name or username or f"id{getattr(actor, 'id', '?')}"


def _status_label(content: ContentService, raw: str | None) -> str:
    if not raw:
        return "—"
    meta = content.texts.statuses.get(raw)
    return f"{meta.emoji} {meta.label}" if meta else raw


def _format_event(event: Any, content: ContentService) -> str:
    when = event.created_at.strftime("%Y-%m-%d %H:%M")
    verb = _EVENT_VERBS.get(event.event_type, event.event_type)
    actor = _actor_label(event)
    head = f"<b>{when}</b> · {actor} · {verb}"

    et = event.event_type
    if et == LeadEventType.STATUS_CHANGED:
        old_label = _status_label(content, event.old_value)
        new_label = _status_label(content, event.new_value)
        return f"{head}\n  {old_label} → {new_label}"
    if et == LeadEventType.LEAD_DELETED:
        old_label = _status_label(content, event.old_value)
        return f"{head}\n  было: {old_label}"
    if et == LeadEventType.COMMENT_ADDED:
        snippet = (event.new_value or "").strip()
        if len(snippet) > 120:
            snippet = snippet[:117] + "…"
        return f"{head}\n  «{snippet}»" if snippet else head
    if et == LeadEventType.ADMIN_ASSIGNED:
        return f"{head}\n  → id{event.new_value}" if event.new_value else head
    if et == LeadEventType.LEAD_CREATED:
        return head
    if et == LeadEventType.FILE_UPLOADED:
        return head
    if et == LeadEventType.CLIENT_CANCELLED:
        snippet = (event.new_value or "").strip()
        return f"{head}\n  причина: {snippet}" if snippet else head
    # Fallback for unknown event types (future-proofing).
    if event.new_value:
        return f"{head}\n  {event.new_value}"
    return head


def render_admin_lead_timeline(
    *,
    content: ContentService,
    public_id: str,
    events: list[Any],
    stack: Sequence[str],
) -> Screen:
    lines = [f"📜 <b>История заявки №{public_id}</b>"]
    if not events:
        lines.append("\nСобытий пока нет.")
    else:
        lines.append("")
        for ev in events:
            lines.append(_format_event(ev, content))
            lines.append("")

    text = "\n".join(lines).rstrip()
    # 4096-char Telegram message limit guard — trim oldest events first if needed.
    while len(text) > 3800 and len(events) > 1:
        events = events[1:]
        lines = [f"📜 <b>История заявки №{public_id}</b>", "(показаны последние записи)\n"]
        for ev in events:
            lines.append(_format_event(ev, content))
            lines.append("")
        text = "\n".join(lines).rstrip()

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
    return Screen(screen_id=ADMIN_LEAD_TIMELINE_SCREEN_ID, text=text, keyboard=keyboard)
