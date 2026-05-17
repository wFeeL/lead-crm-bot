from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.routers.user.menu import render_and_show_main_menu
from app.bot.ui.navigation import clear_root_message_id
from app.db.repositories.leads import LeadRepository
from app.services.content import ContentService

router = Router(name="start")


@router.message(CommandStart())
async def start(
    message: Message,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    """Fresh /start always creates a new root message."""
    await clear_root_message_id(state)
    repo = LeadRepository(session)
    leads_count = await repo.count_by_user(current_user.id)
    await render_and_show_main_menu(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        content=content,
        leads_count=leads_count,
    )
