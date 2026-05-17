from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.routers.user.menu import render_and_show_main_menu
from app.bot.screens.support import (
    SUPPORT_WRITING_SCREEN_ID,
    SupportCallback,
    render_support_writing,
)
from app.bot.states.support import SupportState
from app.bot.ui.navigation import get_stack, push
from app.bot.ui.render import render_screen
from app.db.repositories.leads import LeadRepository
from app.services.content import ContentService

router = Router(name="support")


@router.callback_query(SupportCallback.filter())
async def handle_support_action(
    callback: CallbackQuery,
    callback_data: SupportCallback,
    state: FSMContext,
    content: ContentService,
) -> None:
    if callback_data.action == "write":
        await push(state, SUPPORT_WRITING_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_support_writing(content=content, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        # render_screen applies screen.next_state = SupportState.writing_message
    await callback.answer()


@router.message(StateFilter(SupportState.writing_message))
async def handle_support_message(
    message: Message,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    """Accept the user's support message; for Step 2 this is a stub.

    Step 4 will replace the stub with actual LeadService.create_lead(source='support', ...)
    once the support category exists in the DB (seeded via categories.yaml).
    """
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, отправьте текст сообщения.")
        return

    preview = text[:200] + ("…" if len(text) > 200 else "")
    await message.answer(
        f"✉️ Спасибо! Ваше сообщение отправлено менеджеру.\n\n<i>Текст:</i> {preview}"
    )
    # Reset to main menu.
    await state.set_state(None)
    repo = LeadRepository(session)
    leads_count = await repo.count_by_user(current_user.id)
    await render_and_show_main_menu(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        content=content,
        leads_count=leads_count,
    )
