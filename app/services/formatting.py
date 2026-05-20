"""Human-readable formatters for leads.

Shared helpers used by NotificationService (admin Telegram notification +
email body). Per-screen Telegram messages (admin_lead_detail, my_lead_detail)
have their own renderers — they need the live ContentService for localised
status / priority labels.
"""

from app.core.constants import STATUS_EMOJIS, STATUS_TITLES
from app.db.models.lead import Lead


def lead_title(lead: Lead) -> str:
    return f"Заявка №{lead.public_id or lead.id}"


def status_label(status: str) -> str:
    emoji = STATUS_EMOJIS.get(status, "•")
    title = STATUS_TITLES.get(status, status)
    return f"{emoji} {title}"


def _answer_label(answer) -> str:
    """Prefer the full question text; fall back to the key for legacy answers."""
    question = getattr(answer, "question", None)
    question_text = getattr(question, "question_text", None) if question else None
    return question_text or answer.key


def _admin_label(admin) -> str:
    if admin is None:
        return "—"
    name = (admin.first_name or "").strip()
    username = f"@{admin.username}" if getattr(admin, "username", None) else ""
    if name and username:
        return f"{name} {username}"
    return name or username or f"#{admin.id}"


def _format_answers(lead: Lead) -> list[str]:
    """Return the answers block as a list of lines. Empty list = omit entirely.

    Each Q+A pair takes two lines (question then bullet + answer) so the
    structure reads like a friendly form, not a wall of "key: value" output.
    """
    answers = list(getattr(lead, "answers", None) or [])
    if not answers:
        return []
    lines = ["<b>📝 Ответы:</b>"]
    for answer in answers:
        value = answer.value_text or answer.value_json or "—"
        lines.append("")
        lines.append(f"<b>{_answer_label(answer)}</b>")
        lines.append(f"  └ {value}")
    return lines


def _format_comments(lead: Lead, *, include_internal: bool) -> list[str]:
    """Return the comments block as a list of lines. Empty list = omit entirely."""
    comments = [
        comment
        for comment in sorted(getattr(lead, "comments", None) or [], key=lambda item: item.id or 0)
        if include_internal or not comment.is_internal
    ]
    if not comments:
        return []
    lines = ["<b>💬 Комментарии:</b>"]
    for comment in comments:
        visibility = "внутренний" if comment.is_internal else "клиенту"
        author = _admin_label(getattr(comment, "admin", None))
        lines.append(f"• <i>{author}</i> ({visibility}): {comment.text}")
    return lines


def format_lead_summary(lead: Lead) -> str:
    """Admin-facing summary used by NotificationService.

    Layout:

        Заявка №TG-000042

        Статус: 🆕 Новая
        Категория: ...
        Клиент: ... / @username
        Телефон: ...

        📝 Ответы:

        <Вопрос>
          └ <Ответ>

        💬 Комментарии:
        • ...

    Empty fields are omitted (the support flow has no phone/files/comments,
    for example). The free-text Описание field is suppressed when structured
    answers are present — otherwise it would just repeat them.
    """
    lines: list[str] = [f"<b>{lead_title(lead)}</b>", ""]
    lines.append(f"Статус: {status_label(lead.status)}")

    if lead.assigned_admin_id is not None:
        lines.append(f"Ответственный: #{lead.assigned_admin_id}")

    category = lead.category.title if lead.category else str(lead.category_id)
    lines.append(f"Категория: {category}")

    username = f"@{lead.user.username}" if lead.user and lead.user.username else None
    client_parts = [p for p in (lead.contact_name, username) if p]
    if client_parts:
        lines.append("Клиент: " + " / ".join(client_parts))

    if lead.contact_phone:
        lines.append(f"Телефон: {lead.contact_phone}")

    answer_lines = _format_answers(lead)

    # Описание is built from concatenated answers in lead_create.py, so it
    # would just duplicate the Ответы block. Show it only when answers are
    # genuinely missing (e.g. seeded / imported leads).
    if lead.description and not answer_lines:
        lines.append(f"Описание: {lead.description}")

    files = list(getattr(lead, "files", None) or [])
    if files:
        lines.append(f"📎 Файлов: {len(files)}")

    if answer_lines:
        lines.append("")
        lines.extend(answer_lines)

    comment_lines = _format_comments(lead, include_internal=True)
    if comment_lines:
        lines.append("")
        lines.extend(comment_lines)

    return "\n".join(lines)
