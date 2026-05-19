"""Translate human-readable period keys into datetime ranges.

Used by the admin lead list to bridge the simple FSM-stored string
(``today``/``yesterday``/``week``/``month``/``all``) and the timestamp
boundaries the repository wants.
"""

from datetime import UTC, datetime, time, timedelta

# (date_from, date_to) — both inclusive, in UTC. ``None`` means "no bound".
DateRange = tuple[datetime | None, datetime | None]


def resolve_period(period: str | None, *, now: datetime | None = None) -> DateRange:
    """Return the ``(start, end)`` UTC range for a stored period key.

    Unknown / missing / ``"all"`` keys map to ``(None, None)`` — i.e. no filter.
    """
    if period in (None, "", "all"):
        return (None, None)

    base = (now or datetime.now(UTC)).astimezone(UTC)
    today = base.date()

    if period == "today":
        start = datetime.combine(today, time.min, tzinfo=UTC)
        end = datetime.combine(today, time.max, tzinfo=UTC)
        return (start, end)
    if period == "yesterday":
        y = today - timedelta(days=1)
        start = datetime.combine(y, time.min, tzinfo=UTC)
        end = datetime.combine(y, time.max, tzinfo=UTC)
        return (start, end)
    if period == "week":
        # Trailing 7-day window (inclusive of "today").
        start = datetime.combine(today - timedelta(days=6), time.min, tzinfo=UTC)
        end = datetime.combine(today, time.max, tzinfo=UTC)
        return (start, end)
    if period == "month":
        start = datetime.combine(today - timedelta(days=29), time.min, tzinfo=UTC)
        end = datetime.combine(today, time.max, tzinfo=UTC)
        return (start, end)

    # Unknown key — be liberal, return no filter.
    return (None, None)


def period_label(period: str | None) -> str:
    """Short human label, used in screen titles."""
    return {
        "today": "Сегодня",
        "yesterday": "Вчера",
        "week": "Неделя",
        "month": "Месяц",
    }.get(period or "", "Все время")
