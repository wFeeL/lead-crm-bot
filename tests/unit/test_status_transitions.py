import pytest
from app.core.constants import ALLOWED_STATUS_TRANSITIONS, LeadStatus
from app.core.exceptions import InvalidStatusTransitionError
from app.services.status import assert_status_transition

_ALLOWED_PAIRS = [
    (current.value, target.value)
    for current, targets in ALLOWED_STATUS_TRANSITIONS.items()
    for target in targets
]
_REJECTED_PAIRS = [
    (current.value, target.value)
    for current in LeadStatus
    for target in LeadStatus
    if target not in ALLOWED_STATUS_TRANSITIONS[current] and current != target
]


@pytest.mark.parametrize(("current", "target"), _ALLOWED_PAIRS)
def test_allowed_transition_is_permitted(current: str, target: str) -> None:
    """Every transition declared in ALLOWED_STATUS_TRANSITIONS must pass the guard."""
    assert_status_transition(current, target)


@pytest.mark.parametrize(("current", "target"), _REJECTED_PAIRS)
def test_disallowed_transition_is_rejected(current: str, target: str) -> None:
    """Every other transition (incl. backwards from terminal) must raise."""
    with pytest.raises(InvalidStatusTransitionError):
        assert_status_transition(current, target)


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(InvalidStatusTransitionError):
        assert_status_transition(LeadStatus.NEW, "archived")
