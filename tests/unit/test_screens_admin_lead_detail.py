from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.bot.screens.admin_lead_detail import (
    ADMIN_LEAD_DETAIL_SCREEN_ID,
    AdminDetailCallback,
    render_admin_lead_detail,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def _fake_lead(
    lead_id=1,
    public_id="TG-000001",
    status="new",
    priority="normal",
    description="Some task",
    close_reason=None,
    assigned_admin_id=None,
    assigned_admin=None,
    contact_phone="@user",
    contact_username=None,
    category_title="Боты",
    answers=None,
    comments=None,
    files=None,
    user=None,
):
    return SimpleNamespace(
        id=lead_id,
        public_id=public_id,
        status=status,
        priority=priority,
        description=description,
        close_reason=close_reason,
        assigned_admin_id=assigned_admin_id,
        assigned_admin=assigned_admin,
        contact_phone=contact_phone,
        contact_username=contact_username,
        category=SimpleNamespace(title=category_title),
        created_at=datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC),
        answers=answers or [],
        comments=comments or [],
        files=files or [],
        user=user,
    )


STACK = ["admin_menu", "admin_lead_list", "admin_lead_detail"]


def test_render_admin_lead_detail_structure():
    lead = _fake_lead(public_id="TG-000042")
    screen = render_admin_lead_detail(content=_content(), lead=lead, stack=STACK)
    assert screen.screen_id == ADMIN_LEAD_DETAIL_SCREEN_ID
    assert "TG-000042" in screen.text
    assert "Боты" in screen.text


def _extract_status_values(screen) -> list[str]:
    """Extract 'value' from adm_det:set_status:lead_id:value callbacks."""
    values = []
    for row in screen.keyboard.inline_keyboard:
        for btn in row:
            cd = btn.callback_data
            # format: adm_det:set_status:<lead_id>:<value>
            if cd.startswith("adm_det:set_status:"):
                parts = cd.split(":")
                if len(parts) == 4:
                    values.append(parts[3])
    return values


def _extract_priority_values(screen) -> list[str]:
    """Extract 'value' from adm_det:set_priority:lead_id:value callbacks."""
    values = []
    for row in screen.keyboard.inline_keyboard:
        for btn in row:
            cd = btn.callback_data
            # format: adm_det:set_priority:<lead_id>:<value>
            if cd.startswith("adm_det:set_priority:"):
                parts = cd.split(":")
                if len(parts) == 4:
                    values.append(parts[3])
    return values


def test_render_admin_lead_detail_new_status_buttons():
    """Status=NEW shows CONTACTED, IN_PROGRESS in status row; REJECTED in close row; no DONE."""
    lead = _fake_lead(status="new")
    screen = render_admin_lead_detail(content=_content(), lead=lead, stack=STACK)
    status_values = _extract_status_values(screen)

    # NEW → {CONTACTED, IN_PROGRESS, REJECTED, CANCELLED} per ALLOWED_STATUS_TRANSITIONS
    assert "contacted" in status_values
    assert "in_progress" in status_values
    assert "rejected" in status_values
    # DONE is NOT in NEW's allowed transitions
    assert "done" not in status_values


def test_render_admin_lead_detail_contacted_status_buttons():
    """Status=CONTACTED shows IN_PROGRESS, WAITING in status row; DONE, REJECTED in close row."""
    lead = _fake_lead(status="contacted")
    screen = render_admin_lead_detail(content=_content(), lead=lead, stack=STACK)
    status_values = _extract_status_values(screen)

    assert "in_progress" in status_values
    assert "waiting" in status_values
    assert "done" in status_values
    assert "rejected" in status_values


def test_render_admin_lead_detail_unassigned_shows_take_button():
    lead = _fake_lead(assigned_admin_id=None)
    screen = render_admin_lead_detail(content=_content(), lead=lead, stack=STACK)
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("Взять себе" in lbl for lbl in labels)


def test_render_admin_lead_detail_assigned_hides_take_button():
    lead = _fake_lead(assigned_admin_id=7)
    screen = render_admin_lead_detail(content=_content(), lead=lead, stack=STACK)
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert all("Взять себе" not in lbl for lbl in labels)


def test_render_admin_lead_detail_priority_row_marks_current():
    lead = _fake_lead(priority="high")
    screen = render_admin_lead_detail(content=_content(), lead=lead, stack=STACK)
    # Find priority buttons (set_priority action): format adm_det:set_priority:lead_id:value
    prio_labels = []
    for row in screen.keyboard.inline_keyboard:
        for btn in row:
            if btn.callback_data.startswith("adm_det:set_priority:"):
                prio_labels.append(btn.text)
    # One of the priority buttons should be marked with ✓
    assert any("✓" in lbl for lbl in prio_labels)


def test_render_admin_lead_detail_shows_full_question_text_not_key():
    """Bug fix: admin must see human-readable question text, never the English key."""
    answer = SimpleNamespace(
        key="biz_name",
        value_text="ООО Ромашка",
        value_json=None,
        question=SimpleNamespace(question_text="Как называется ваш бизнес?"),
    )
    lead = _fake_lead(answers=[answer])
    screen = render_admin_lead_detail(content=_content(), lead=lead, stack=STACK)
    assert "Как называется ваш бизнес?" in screen.text
    assert "ООО Ромашка" in screen.text
    # The raw key must not leak into the rendered text.
    assert "biz_name" not in screen.text


def test_render_admin_lead_detail_shows_internal_comments():
    """Bug fix: internal comments must be visible in admin detail."""
    admin = SimpleNamespace(id=7, first_name="Иван", username="ivan_admin")
    comment = SimpleNamespace(
        id=1,
        text="Клиент перезвонит после 18:00",
        is_internal=True,
        admin=admin,
    )
    lead = _fake_lead(comments=[comment])
    screen = render_admin_lead_detail(content=_content(), lead=lead, stack=STACK)
    assert "Комментарии" in screen.text
    assert "Клиент перезвонит после 18:00" in screen.text
    assert "внутренний" in screen.text
    assert "Иван" in screen.text


def test_admin_detail_callbacks_pack():
    prefix = "adm_det:"
    assert (
        AdminDetailCallback(action="set_status", lead_id=1, value="done").pack().startswith(prefix)
    )
    assert (
        AdminDetailCallback(action="set_priority", lead_id=1, value="high")
        .pack()
        .startswith(prefix)
    )
    assert AdminDetailCallback(action="comment_internal", lead_id=1).pack().startswith(prefix)
    assert AdminDetailCallback(action="assign_me", lead_id=1).pack().startswith(prefix)
