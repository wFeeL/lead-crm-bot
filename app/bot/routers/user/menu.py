from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.screens.faq import FAQ_SCREEN_ID, render_faq
from app.bot.screens.main_menu import MainMenuCallback, render_main_menu
from app.bot.screens.my_leads import MY_LEADS_SCREEN_ID, render_my_leads
from app.bot.screens.support import SUPPORT_SCREEN_ID, render_support
from app.bot.ui.navigation import get_stack, go_home, push
from app.bot.ui.render import render_screen
from app.db.repositories.leads import LeadRepository
from app.services.content import ContentService

router = Router(name="menu")


async def render_and_show_main_menu(
    *,
    bot,
    chat_id: int,
    state: FSMContext,
    content: ContentService,
    leads_count: int,
) -> None:
    """Render MAIN_MENU as the new root and reset nav stack to [main_menu]."""
    await go_home(state)  # nav_stack = [main_menu]
    screen = render_main_menu(content=content, leads_count=leads_count)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


@router.callback_query(MainMenuCallback.filter())
async def handle_main_menu(
    callback: CallbackQuery,
    callback_data: MainMenuCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    repo = LeadRepository(session)

    if callback_data.action == "create_lead":
        # Step 3 will wire lead_create flow onto the Screen system. Until then,
        # alert the user gracefully.
        await callback.answer("Скоро будет (Step 3).", show_alert=True)
        return

    if callback_data.action == "my_leads":
        await push(state, MY_LEADS_SCREEN_ID)
        page_size = content.config.ui.page_size_my_leads
        leads = await repo.list_by_user(current_user.id, limit=page_size, offset=0)
        total = await repo.count_by_user(current_user.id)
        stack = await get_stack(state)
        screen = render_my_leads(
            content=content, leads=leads, page=1, total=total, stack=stack
        )
    elif callback_data.action == "support":
        await push(state, SUPPORT_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_support(content=content, stack=stack)
    elif callback_data.action == "faq":
        await push(state, FAQ_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_faq(content=content, stack=stack)
    else:
        await callback.answer()
        return

    await render_screen(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        screen=screen,
    )
    await callback.answer()
