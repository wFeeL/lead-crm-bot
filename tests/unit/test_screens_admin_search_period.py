"""Tests for the two new admin screens: search prompt + period picker."""

from app.bot.screens.admin_period_picker import (
    ADMIN_PERIOD_PICKER_SCREEN_ID,
    AdminPeriodCallback,
    render_admin_period_picker,
)
from app.bot.screens.admin_search_prompt import (
    ADMIN_SEARCH_PROMPT_SCREEN_ID,
    render_admin_search_prompt,
)
from app.bot.states.admin_flow import AdminFlowState
from app.bot.ui.callbacks import NavCallback

STACK = ["admin_menu", "admin_search_prompt"]


def test_search_prompt_renders_and_sets_state():
    screen = render_admin_search_prompt(stack=STACK)
    assert screen.screen_id == ADMIN_SEARCH_PROMPT_SCREEN_ID
    # The prompt mentions the supported query formats so admins know what to type.
    for keyword in ("номер", "username", "TG-", "Telegram-ID"):
        assert keyword in screen.text
    # Sets FSM into searching so the next text message becomes the query.
    assert screen.next_state == AdminFlowState.searching
    # Has at least a back / home button.
    callbacks = [btn.callback_data for row in screen.keyboard.inline_keyboard for btn in row]
    assert NavCallback(action="back").pack() in callbacks


def test_period_picker_lists_all_five_options_and_marks_current():
    screen = render_admin_period_picker(current_period="week", stack=["admin_menu", "x"])
    assert screen.screen_id == ADMIN_PERIOD_PICKER_SCREEN_ID
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    for needle in ("Сегодня", "Вчера", "7 дней", "30 дней", "Все время"):
        assert any(needle in lbl for lbl in labels), f"missing {needle!r}"
    # Only one button has the ✓ marker (the current selection).
    marked = [lbl for lbl in labels if lbl.startswith("✓")]
    assert len(marked) == 1
    assert "7 дней" in marked[0]


def test_period_picker_marks_all_when_current_is_none():
    screen = render_admin_period_picker(current_period=None, stack=["admin_menu", "x"])
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    marked = [lbl for lbl in labels if lbl.startswith("✓")]
    assert len(marked) == 1
    assert "Все время" in marked[0]


def test_period_callback_packs_with_short_key():
    cb = AdminPeriodCallback(period="today").pack()
    assert cb.startswith("adm_per:today")
