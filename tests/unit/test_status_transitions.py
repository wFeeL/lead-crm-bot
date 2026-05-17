import pytest
from app.core.constants import LeadStatus
from app.core.exceptions import InvalidStatusTransitionError
from app.services.status import assert_status_transition, available_statuses


def test_allowed_status_transition() -> None:
    assert_status_transition(LeadStatus.NEW, LeadStatus.IN_PROGRESS)


def test_invalid_status_transition_is_rejected() -> None:
    with pytest.raises(InvalidStatusTransitionError):
        assert_status_transition(LeadStatus.DONE, LeadStatus.NEW)


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(InvalidStatusTransitionError):
        assert_status_transition(LeadStatus.NEW, "archived")


def test_available_statuses_for_waiting() -> None:
    assert set(available_statuses(LeadStatus.WAITING)) == {
        LeadStatus.IN_PROGRESS,
        LeadStatus.DONE,
        LeadStatus.REJECTED,
    }
