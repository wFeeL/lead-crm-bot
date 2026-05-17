from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_COMMENT_PROMPT_SCREEN_ID = "admin_comment_prompt"


def render_admin_comment_prompt(
    *,
    content: ContentService,
    lead_public_id: str,
    is_internal: bool,
    stack: Sequence[str],
) -> Screen:
    kind = "📝 Внутренний комментарий" if is_internal else "💬 Ответ клиенту"
    text = f"{kind} к заявке №{lead_public_id}\n\nНапишите текст одним сообщением."
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
    return Screen(screen_id=ADMIN_COMMENT_PROMPT_SCREEN_ID, text=text, keyboard=keyboard)
