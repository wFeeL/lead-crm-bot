from uuid import uuid4

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
from app.core.config import get_settings
from app.db.repositories.forms import FormRepository
from app.db.repositories.leads import LeadRepository
from app.schemas.lead import LeadAnswerInput, LeadCreateInput
from app.services.content import ContentService
from app.services.leads import LeadService

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
    """Accept the user's support message and create a real lead with source='support'."""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, отправьте текст сообщения.")
        return

    form_repo = FormRepository(session)
    category = await form_repo.get_category_by_slug("support")
    if category is None:
        # Profile missing support category — degrade gracefully.
        await message.answer("✉️ Сообщение получено. Менеджер свяжется.")
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
        return

    form = await form_repo.get_active_form(category.id)
    question = form.questions[0] if form and form.questions else None

    answers = []
    if question is not None:
        answers.append(
            LeadAnswerInput(question_id=question.id, key=question.key, value_text=text)
        )

    payload = LeadCreateInput(
        user_id=current_user.id,
        category_id=category.id,
        submission_key=uuid4().hex,
        title="Связь с менеджером",
        description=text,
        contact_name=current_user.first_name,
        contact_phone=current_user.phone,
        contact_username=current_user.username,
        answers=answers,
        files=[],
        source="support",
    )

    service = LeadService(session, get_settings())
    lead = await service.create_lead(payload)

    if getattr(lead, "created_now", True):
        from app.services.notifications import NotificationService

        notifier = NotificationService(message.bot, get_settings())
        await notifier.notify_new_lead(lead)

    await message.answer(
        f"✉️ Спасибо! Ваше обращение №{lead.public_id} отправлено менеджеру."
    )
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
