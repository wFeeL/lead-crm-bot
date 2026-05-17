import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.core.exceptions import ValidationError

PHONE_RE = re.compile(r"^\+?[0-9][0-9\s()\-]{6,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_phone(value: str) -> str:
    cleaned = value.strip()
    if not PHONE_RE.match(cleaned):
        raise ValidationError("invalid phone number")
    return cleaned


def validate_email(value: str) -> str:
    cleaned = value.strip()
    if not EMAIL_RE.match(cleaned):
        raise ValidationError("invalid email")
    return cleaned


def validate_number(value: str) -> str:
    cleaned = value.strip().replace(",", ".")
    try:
        Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValidationError("invalid number") from exc
    return cleaned


def validate_date(value: str) -> str:
    cleaned = value.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValidationError("invalid date")


def validate_time(value: str) -> str:
    cleaned = value.strip()
    for fmt in ("%H:%M", "%H.%M"):
        try:
            return datetime.strptime(cleaned, fmt).time().strftime("%H:%M")
        except ValueError:
            continue
    raise ValidationError("invalid time")
