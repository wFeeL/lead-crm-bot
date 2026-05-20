from aiogram.types import InlineKeyboardButton
from app.bot.ui.footer import nav_footer


def test_nav_footer_empty_stack_has_home_only():
    rows = nav_footer(stack=[])
    assert len(rows) == 1
    labels = [btn.text for btn in rows[0]]
    assert any("Меню" in lbl for lbl in labels)
    assert all("Назад" not in lbl for lbl in labels)
    # Cancel was removed — it duplicated Back visually.
    assert all("Отмена" not in lbl for lbl in labels)


def test_nav_footer_single_screen_no_back():
    """At the bottom of the stack we only show Home — no Back."""
    rows = nav_footer(stack=["main_menu"])
    labels = [btn.text for btn in rows[0]]
    assert all("Назад" not in lbl for lbl in labels)
    assert any("Меню" in lbl for lbl in labels)
    assert all("Отмена" not in lbl for lbl in labels)


def test_nav_footer_with_history_has_back_and_home():
    rows = nav_footer(stack=["main_menu", "faq"])
    labels = [btn.text for btn in rows[0]]
    assert any("Назад" in lbl for lbl in labels)
    assert any("Меню" in lbl for lbl in labels)
    assert all("Отмена" not in lbl for lbl in labels)


def test_nav_footer_extra_buttons_prepended():
    extra = [[InlineKeyboardButton(text="Custom", callback_data="custom:x")]]
    rows = nav_footer(stack=["main_menu", "faq"], extra=extra)
    assert len(rows) == 2
    assert rows[0][0].text == "Custom"
    assert any("Назад" in btn.text for btn in rows[-1])
