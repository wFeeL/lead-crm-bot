from app.core.constants import ALLOWED_STATUS_TRANSITIONS, LeadStatus
from app.core.exceptions import InvalidStatusTransitionError


def assert_status_transition(current: str, target: str) -> None:
    try:
        current_status = LeadStatus(current)
        target_status = LeadStatus(target)
    except ValueError as exc:
        raise InvalidStatusTransitionError(f"unknown status: {current} -> {target}") from exc
    if target_status not in ALLOWED_STATUS_TRANSITIONS[current_status]:
        raise InvalidStatusTransitionError(f"cannot transition from {current} to {target}")
