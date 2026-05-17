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
