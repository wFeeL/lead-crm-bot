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


def _format_answers(lead: Lead) -> str:
    if not lead.answers:
        return "Ответы: нет"
    lines = ["Ответы:"]
    for answer in lead.answers:
        value = answer.value_text or answer.value_json or "—"
        lines.append(f"• {_answer_label(answer)}: {value}")
    return "\n".join(lines)


def _format_comments(lead: Lead, *, include_internal: bool) -> str:
    comments = [
        comment
        for comment in sorted(lead.comments, key=lambda item: item.id or 0)
        if include_internal or not comment.is_internal
    ]
    if not comments:
        return "Комментарии: нет"
    lines = ["Комментарии:"]
    for comment in comments:
        visibility = "внутренний" if comment.is_internal else "клиенту"
        author = _admin_label(getattr(comment, "admin", None))
        lines.append(f"• {author} ({visibility}): {comment.text}")
    return "\n".join(lines)


def format_lead_summary(lead: Lead) -> str:
    username = f"@{lead.user.username}" if lead.user and lead.user.username else "не указан"
    category = lead.category.title if lead.category else str(lead.category_id)
    assigned = (
        f"#{lead.assigned_admin_id}" if lead.assigned_admin_id is not None else "не назначена"
    )
    return (
        f"{lead_title(lead)}\n\n"
        f"Статус: {status_label(lead.status)}\n"
        f"Ответственный: {assigned}\n"
        f"Категория: {category}\n"
        f"Клиент: {lead.contact_name or 'не указан'} / {username}\n"
        f"Телефон: {lead.contact_phone or 'не указан'}\n"
        f"Описание: {lead.description}\n"
        f"Файлов: {len(lead.files)}\n\n"
        f"{_format_answers(lead)}\n\n"
        f"{_format_comments(lead, include_internal=True)}"
    )


def format_public_lead_line(lead: Lead) -> str:
    category = lead.category.title if lead.category else str(lead.category_id)
    return f"{lead.public_id or lead.id}: {category}, {status_label(lead.status)}"


def format_user_lead_detail(lead: Lead) -> str:
    category = lead.category.title if lead.category else str(lead.category_id)
    return (
        f"{lead_title(lead)}\n\n"
        f"Статус: {status_label(lead.status)}\n"
        f"Категория: {category}\n"
        f"Контакт: {lead.contact_phone or lead.contact_username or 'не указан'}\n"
        f"Описание: {lead.description}\n"
        f"Файлов: {len(lead.files)}\n\n"
        f"{_format_answers(lead)}\n\n"
        f"{_format_comments(lead, include_internal=False)}"
    )
