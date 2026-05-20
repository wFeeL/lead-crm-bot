from app.core.constants import STATUS_EMOJIS, STATUS_TITLES
from app.db.models.lead import Lead


def lead_title(lead: Lead) -> str:
    return f"Заявка {lead.public_id or lead.id}"


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
    """Return the answers block as a list of lines. Empty list = omit entirely."""
    answers = list(getattr(lead, "answers", None) or [])
    if not answers:
        return []
    lines = ["Ответы:"]
    for answer in answers:
        value = answer.value_text or answer.value_json or "—"
        lines.append(f"• {_answer_label(answer)}: {value}")
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
    lines = ["Комментарии:"]
    for comment in comments:
        visibility = "внутренний" if comment.is_internal else "клиенту"
        author = _admin_label(getattr(comment, "admin", None))
        lines.append(f"• {author} ({visibility}): {comment.text}")
    return lines


def format_lead_summary(lead: Lead) -> str:
    """Admin-facing summary. Empty fields are omitted to avoid clutter for
    leads where the user couldn't fill them in (notably the support/💬
    Менеджер flow has no phone, no files, no comments)."""
    lines: list[str] = [lead_title(lead), ""]
    lines.append(f"Статус: {status_label(lead.status)}")

    # Only show "Ответственный" if assigned.
    if lead.assigned_admin_id is not None:
        lines.append(f"Ответственный: #{lead.assigned_admin_id}")

    category = lead.category.title if lead.category else str(lead.category_id)
    lines.append(f"Категория: {category}")

    # Client identity — at least one of name / username must exist.
    username = f"@{lead.user.username}" if lead.user and lead.user.username else None
    client_parts = [p for p in (lead.contact_name, username) if p]
    if client_parts:
        lines.append("Клиент: " + " / ".join(client_parts))

    # Phone — only if the user actually shared one (support flow doesn't).
    if lead.contact_phone:
        lines.append(f"Телефон: {lead.contact_phone}")

    if lead.description:
        lines.append(f"Описание: {lead.description}")

    # File count — only when files exist.
    files = list(getattr(lead, "files", None) or [])
    if files:
        lines.append(f"Файлов: {len(files)}")

    answer_lines = _format_answers(lead)
    if answer_lines:
        lines.append("")
        lines.extend(answer_lines)

    comment_lines = _format_comments(lead, include_internal=True)
    if comment_lines:
        lines.append("")
        lines.extend(comment_lines)

    return "\n".join(lines)
