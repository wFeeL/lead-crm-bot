from aiogram.types import InlineKeyboardButton
from app.bot.ui.footer import nav_footer


def test_nav_footer_empty_stack_has_only_cancel():
    rows = nav_footer(stack=[])
    assert len(rows) == 1
    labels = [btn.text for btn in rows[0]]
    assert any("Отмена" in lbl for lbl in labels)
    assert all("Назад" not in lbl for lbl in labels)
    assert all("Меню" not in lbl for lbl in labels)


def test_nav_footer_single_screen_no_back():
    rows = nav_footer(stack=["main_menu"])
    labels = [btn.text for btn in rows[0]]
    assert all("Назад" not in lbl for lbl in labels)
    assert any("Меню" in lbl for lbl in labels)
    assert any("Отмена" in lbl for lbl in labels)


def test_nav_footer_with_history_has_back_home_cancel():
    rows = nav_footer(stack=["main_menu", "faq"])
    labels = [btn.text for btn in rows[0]]
    assert any("Назад" in lbl for lbl in labels)
    assert any("Меню" in lbl for lbl in labels)
    assert any("Отмена" in lbl for lbl in labels)


def test_nav_footer_extra_buttons_prepended():
    extra = [[InlineKeyboardButton(text="Custom", callback_data="custom:x")]]
    rows = nav_footer(stack=["main_menu", "faq"], extra=extra)
    assert len(rows) == 2
    assert rows[0][0].text == "Custom"
    assert any("Назад" in btn.text for btn in rows[-1])
