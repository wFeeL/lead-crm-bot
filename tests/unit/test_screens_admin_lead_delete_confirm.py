from app.bot.screens.admin_lead_delete_confirm import (
    ADMIN_LEAD_DELETE_CONFIRM_SCREEN_ID,
    AdminLeadDeleteCallback,
    render_admin_lead_delete_confirm,
)

STACK = ["admin_menu", "admin_lead_list", "admin_lead_detail", "admin_lead_delete_confirm"]


def test_delete_confirm_renders_warning_and_confirm_button():
    """Screen has the destructive button + nav-footer Back. Cancel = Back, not a duplicate."""
    screen = render_admin_lead_delete_confirm(public_id="TG-000042", lead_id=42, stack=STACK)
    assert screen.screen_id == ADMIN_LEAD_DELETE_CONFIRM_SCREEN_ID
    assert "TG-000042" in screen.text
    assert "Удалить" in screen.text
    callbacks = [btn.callback_data for row in screen.keyboard.inline_keyboard for btn in row]
    assert any(cb.startswith("adm_del:confirm:42") for cb in callbacks)
    # Cancel is provided by the universal nav-footer Back button.
    from app.bot.ui.callbacks import NavCallback

    assert NavCallback(action="back").pack() in callbacks
    # No duplicate cancel-via-adm_del to avoid two visually-equivalent back buttons.
    assert not any(cb.startswith("adm_del:cancel:") for cb in callbacks)


def test_delete_callbacks_pack_with_lead_id():
    cb = AdminLeadDeleteCallback(action="confirm", lead_id=7).pack()
    assert cb.startswith("adm_del:confirm:7")


def test_admin_detail_includes_delete_button():
    """admin_lead_detail must expose the new 🗑 Удалить action."""
    from datetime import UTC, datetime
    from pathlib import Path
    from types import SimpleNamespace

    from app.bot.screens.admin_lead_detail import render_admin_lead_detail
    from app.services.content import ContentService

    content_dir = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"
    content = ContentService(ContentService.load(content_dir))
    lead = SimpleNamespace(
        id=1,
        public_id="TG-000001",
        status="new",
        priority="normal",
        description="t",
        close_reason=None,
        assigned_admin_id=None,
        assigned_admin=None,
        contact_phone="@u",
        contact_username=None,
        category=SimpleNamespace(title="C"),
        created_at=datetime(2026, 5, 17, 10, 0, tzinfo=UTC),
        answers=[],
        comments=[],
        files=[],
        user=None,
    )
    screen = render_admin_lead_detail(content=content, lead=lead, stack=["admin_menu", "x", "y"])
    callbacks = [btn.callback_data for row in screen.keyboard.inline_keyboard for btn in row]
    assert any(cb.startswith("adm_det:delete:1") for cb in callbacks)
