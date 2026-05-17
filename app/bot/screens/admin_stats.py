from collections.abc import Sequence
from typing import Any

from aiogram.types import InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen

ADMIN_STATS_SCREEN_ID = "admin_stats"


def render_admin_stats(
    *,
    stats: Any,
    stack: Sequence[str],
) -> Screen:
    """Daily stats screen — body comes from ``LeadService.daily_stats()``."""
    text = (
        f"📊 <b>Статистика дня ({stats.date})</b>\n\n"
        f"🆕 Новых: {stats.new}\n"
        f"🛠 В работе: {stats.in_progress}\n"
        f"⏳ Ждут: {stats.waiting}\n"
        f"✅ Завершено: {stats.done}\n"
        f"❌ Отклонено: {stats.rejected}\n"
        f"🚫 Отменено: {stats.cancelled}\n\n"
        f"🏆 Топ-категория: {stats.top_category or '—'}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
    return Screen(screen_id=ADMIN_STATS_SCREEN_ID, text=text, keyboard=keyboard)
