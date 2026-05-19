from app.core.constants import LeadStatus
from app.db.models.lead import Lead, LeadComment
from app.services.formatting import format_lead_summary, status_label


def test_status_label_uses_friendly_text() -> None:
    assert status_label(LeadStatus.IN_PROGRESS) == "🛠 В работе"


def test_lead_summary_includes_internal_comments() -> None:
    """Admin-facing summary is used by NotificationService — must show internal notes."""
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
    assert "internal" in admin_text
    assert "public" in admin_text
