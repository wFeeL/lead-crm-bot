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
        LeadStatus.CONTACTED,
        LeadStatus.IN_PROGRESS,
        LeadStatus.DONE,
        LeadStatus.REJECTED,
        LeadStatus.CANCELLED,
    }


def test_new_can_transition_to_contacted() -> None:
    assert_status_transition(LeadStatus.NEW, LeadStatus.CONTACTED)


def test_contacted_can_transition_to_in_progress() -> None:
    assert_status_transition(LeadStatus.CONTACTED, LeadStatus.IN_PROGRESS)


def test_contacted_can_transition_to_waiting() -> None:
    assert_status_transition(LeadStatus.CONTACTED, LeadStatus.WAITING)


def test_contacted_can_transition_to_done() -> None:
    assert_status_transition(LeadStatus.CONTACTED, LeadStatus.DONE)


def test_contacted_can_transition_to_rejected() -> None:
    assert_status_transition(LeadStatus.CONTACTED, LeadStatus.REJECTED)


def test_contacted_can_transition_to_cancelled() -> None:
    assert_status_transition(LeadStatus.CONTACTED, LeadStatus.CANCELLED)


def test_in_progress_can_transition_to_contacted() -> None:
    assert_status_transition(LeadStatus.IN_PROGRESS, LeadStatus.CONTACTED)


def test_waiting_can_transition_to_contacted() -> None:
    assert_status_transition(LeadStatus.WAITING, LeadStatus.CONTACTED)


def test_contacted_cannot_transition_to_new() -> None:
    with pytest.raises(InvalidStatusTransitionError):
        assert_status_transition(LeadStatus.CONTACTED, LeadStatus.NEW)
