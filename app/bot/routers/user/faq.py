from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.screens.faq import FAQ_ANSWER_SCREEN_ID, FaqCallback, render_faq_answer
from app.bot.ui.navigation import get_stack, push
from app.bot.ui.render import render_screen
from app.services.content import ContentService

router = Router(name="faq")


@router.callback_query(FaqCallback.filter())
async def handle_faq_select(
    callback: CallbackQuery,
    callback_data: FaqCallback,
    state: FSMContext,
    content: ContentService,
) -> None:
    await push(state, FAQ_ANSWER_SCREEN_ID)
    # Remember the open FAQ index so the back-renderer can re-paint this answer
    # when the user returns from a nested screen.
    await state.update_data(faq_current_index=callback_data.index)
    stack = await get_stack(state)
    screen = render_faq_answer(content=content, index=callback_data.index, stack=stack)
    await render_screen(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        screen=screen,
    )
    await callback.answer()
