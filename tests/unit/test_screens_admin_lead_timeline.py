"""Unit tests for the timeline screen renderer."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.bot.screens.admin_lead_timeline import (
    ADMIN_LEAD_TIMELINE_SCREEN_ID,
    render_admin_lead_timeline,
)
from app.core.constants import LeadEventType
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def _ev(event_type, *, when=None, actor=None, old=None, new=None):
    return SimpleNamespace(
        id=1,
        event_type=event_type,
        created_at=when or datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        actor=actor,
        old_value=old,
        new_value=new,
    )


STACK = ["admin_menu", "admin_lead_list", "admin_lead_detail", "admin_lead_timeline"]


def test_render_timeline_empty_events_shows_placeholder():
    screen = render_admin_lead_timeline(
        content=_content(), public_id="TG-000042", events=[], stack=STACK
    )
    assert screen.screen_id == ADMIN_LEAD_TIMELINE_SCREEN_ID
    assert "TG-000042" in screen.text
    assert "Событий пока нет" in screen.text


def test_render_timeline_formats_status_change():
    admin = SimpleNamespace(id=7, first_name="Анна", username="anya_admin")
    events = [
        _ev(LeadEventType.STATUS_CHANGED, actor=admin, old="new", new="in_progress"),
    ]
    screen = render_admin_lead_timeline(
        content=_content(), public_id="TG-000042", events=events, stack=STACK
    )
    # Actor name + status arrow appear in the rendered text.
    assert "Анна" in screen.text
    assert "🆕" in screen.text  # old status emoji from texts.yaml
    assert "🛠" in screen.text  # new status emoji
    assert "→" in screen.text


def test_render_timeline_formats_comment_with_snippet():
    admin = SimpleNamespace(id=7, first_name="Боб", username="bob_admin")
    long_text = "А" * 200
    events = [_ev(LeadEventType.COMMENT_ADDED, actor=admin, new=long_text)]
    screen = render_admin_lead_timeline(
        content=_content(), public_id="X", events=events, stack=STACK
    )
    # Snippet is truncated to ~120 chars with ellipsis.
    assert "…" in screen.text
    assert "Боб" in screen.text


def test_render_timeline_handles_missing_actor():
    """Lead-created event has no admin actor — render must not crash."""
    events = [_ev(LeadEventType.LEAD_CREATED, actor=None)]
    screen = render_admin_lead_timeline(
        content=_content(), public_id="X", events=events, stack=STACK
    )
    assert "система" in screen.text
    assert "создана" in screen.text


def test_render_timeline_trims_when_too_long():
    """A huge events list must still render under Telegram's message limit."""
    admin = SimpleNamespace(id=7, first_name="C", username="c")
    huge_text = "x" * 100
    events = [_ev(LeadEventType.COMMENT_ADDED, actor=admin, new=huge_text) for _ in range(200)]
    screen = render_admin_lead_timeline(
        content=_content(), public_id="X", events=events, stack=STACK
    )
    assert len(screen.text) < 4000
    # Notice text is present when truncation kicked in.
    assert "последние" in screen.text or "Событий" in screen.text
