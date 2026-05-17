from types import SimpleNamespace

from app.bot.screens.admin_stats import ADMIN_STATS_SCREEN_ID, render_admin_stats
from app.bot.ui.callbacks import NavCallback

STACK = ["admin_menu", "admin_stats"]


def _stats(**overrides):
    base = {
        "date": "2026-05-17",
        "new": 3,
        "in_progress": 1,
        "waiting": 2,
        "done": 4,
        "rejected": 0,
        "cancelled": 1,
        "top_category": "Боты",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_admin_stats_renders_counts_and_top_category():
    screen = render_admin_stats(stats=_stats(), stack=STACK)
    assert screen.screen_id == ADMIN_STATS_SCREEN_ID
    assert "2026-05-17" in screen.text
    assert "3" in screen.text  # new
    assert "Боты" in screen.text


def test_admin_stats_shows_dash_when_no_top_category():
    screen = render_admin_stats(stats=_stats(top_category=None), stack=STACK)
    assert "—" in screen.text


def test_admin_stats_includes_back_button():
    """The whole point: admin must be able to return to admin_menu."""
    screen = render_admin_stats(stats=_stats(), stack=STACK)
    callbacks = [btn.callback_data for row in screen.keyboard.inline_keyboard for btn in row]
    assert NavCallback(action="back").pack() in callbacks
