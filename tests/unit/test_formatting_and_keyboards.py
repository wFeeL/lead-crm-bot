from app.bot.keyboards.builders import admin_menu_keyboard, user_lead_detail_keyboard
from app.core.constants import LeadStatus
from app.db.models.lead import Lead, LeadComment
from app.services.formatting import format_lead_summary, format_user_lead_detail, status_label


def test_status_label_uses_friendly_text() -> None:
    assert status_label(LeadStatus.IN_PROGRESS) == "🛠 В работе"


def test_user_detail_hides_internal_comments() -> None:
    lead = Lead(
        id=1,
        public_id="TG-000001",
        user_id=1,
        category_id=1,
        status=LeadStatus.NEW,
        title="Test",
        description="Description",
        source="telegram",
        comments=[
            LeadComment(id=1, lead_id=1, admin_id=10, text="internal", is_internal=True),
            LeadComment(id=2, lead_id=1, admin_id=10, text="public", is_internal=False),
        ],
        files=[],
        answers=[],
    )

    admin_text = format_lead_summary(lead)
    user_text = format_user_lead_detail(lead)

    assert "internal" in admin_text
    assert "public" in admin_text
    assert "internal" not in user_text
    assert "public" in user_text


def test_user_lead_detail_keyboard_has_cancel_for_new_leads() -> None:
    lead = Lead(id=1, user_id=1, category_id=1, status=LeadStatus.NEW, title="T", description="D")

    markup = user_lead_detail_keyboard(lead)
    button_texts = [button.text for row in markup.inline_keyboard for button in row]

    assert "🚫 Отменить заявку" in button_texts
    assert "⬅️ К моим заявкам" in button_texts


def test_admin_menu_has_navigation_actions() -> None:
    markup = admin_menu_keyboard()
    button_texts = [button.text for row in markup.inline_keyboard for button in row]

    assert "📋 Все заявки" in button_texts
    assert "📤 CSV" in button_texts

