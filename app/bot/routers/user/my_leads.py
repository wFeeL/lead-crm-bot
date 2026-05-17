from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.screens.cancel_reason import CancelReasonCallback, render_cancel_reason
from app.bot.screens.my_leads import (
    MY_LEAD_DETAIL_SCREEN_ID,
    MY_LEADS_SCREEN_ID,
    MyLeadDetailCallback,
    MyLeadsCallback,
    render_my_lead_detail,
    render_my_leads,
)
from app.bot.states.cancel import MyLeadCancelState
from app.bot.ui.navigation import get_stack, pop, push
from app.bot.ui.render import render_screen
from app.core.config import get_settings
from app.db.repositories.leads import LeadRepository
from app.services.content import ContentService
from app.services.leads import LeadService

router = Router(name="my_leads")


@router.callback_query(MyLeadsCallback.filter())
async def handle_my_leads(
    callback: CallbackQuery,
    callback_data: MyLeadsCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    repo = LeadRepository(session)
    page_size = content.config.ui.page_size_my_leads

    if callback_data.action == "page":
        leads = await repo.list_by_user(
            current_user.id,
            limit=page_size,
            offset=(callback_data.page - 1) * page_size,
        )
        total = await repo.count_by_user(current_user.id)
        await push(state, MY_LEADS_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_my_leads(
            content=content,
            leads=leads,
            page=callback_data.page,
            total=total,
            stack=stack,
        )
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
    elif callback_data.action == "open":
        lead = await repo.get(callback_data.lead_id)
        if lead is None or lead.user_id != current_user.id:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return
        await push(state, MY_LEAD_DETAIL_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_my_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
    await callback.answer()


@router.callback_query(MyLeadDetailCallback.filter())
async def handle_lead_detail_action(
    callback: CallbackQuery,
    callback_data: MyLeadDetailCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    if callback_data.action == "cancel":
        from app.bot.screens.cancel_reason import MY_LEAD_CANCEL_REASON_SCREEN_ID

        await push(state, MY_LEAD_CANCEL_REASON_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_cancel_reason(content=content, lead_id=callback_data.lead_id, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer()
        return

    elif callback_data.action == "repeat":
        from app.bot.screens.lead_confirm import LEAD_CONFIRM_SCREEN_ID, render_lead_confirm
        from app.bot.states.lead import LeadFormState
        from app.core.exceptions import PermissionDeniedError, ValidationError

        service = LeadService(session, get_settings())
        try:
            draft = await service.build_draft_from_lead(
                lead_id=callback_data.lead_id, actor=current_user
            )
        except (PermissionDeniedError, ValidationError) as exc:
            await callback.answer(str(exc), show_alert=True)
            return

        await state.set_state(LeadFormState.confirming)
        await state.update_data(draft)
        await push(state, LEAD_CONFIRM_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_lead_confirm(content=content, draft=draft, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer()
        return

    else:
        # Unhandled actions (e.g. literal "open" — currently dead) must still
        # acknowledge the callback to clear Telegram's spinner.
        await callback.answer()


@router.callback_query(CancelReasonCallback.filter())
async def handle_cancel_reason(
    callback: CallbackQuery,
    callback_data: CancelReasonCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    if callback_data.action == "custom":
        await state.set_state(MyLeadCancelState.writing_custom_reason)
        await state.update_data({"cancel_target_lead_id": callback_data.lead_id})
        await callback.message.answer("Опишите причину одним сообщением.")
        await callback.answer()
        return

    # action == "pick"
    reasons: list[str] = list(content.texts.close_reasons.cancelled or [])
    if callback_data.index < 0 or callback_data.index >= len(reasons):
        await callback.answer("Ошибка.", show_alert=True)
        return
    reason = reasons[callback_data.index]

    service = LeadService(session, get_settings())
    try:
        await service.cancel_by_client(
            lead_id=callback_data.lead_id, actor=current_user, reason=reason
        )
        await callback.answer("✅ Заявка отменена.")
    except Exception as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    repo = LeadRepository(session)
    lead = await repo.get(callback_data.lead_id)
    if lead is None:
        return
    await pop(state)  # leave the cancel_reason screen
    stack = await get_stack(state)
    screen = render_my_lead_detail(content=content, lead=lead, stack=stack)
    await render_screen(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        screen=screen,
    )


@router.message(StateFilter(MyLeadCancelState.writing_custom_reason))
async def handle_cancel_custom_reason(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user,
    content: ContentService,
) -> None:
    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Пожалуйста, напишите причину.")
        return
    data = await state.get_data()
    lead_id = data.get("cancel_target_lead_id")
    if lead_id is None:
        await message.answer("Внутренняя ошибка. Попробуйте снова через «Мои заявки».")
        await state.set_state(None)
        return

    service = LeadService(session, get_settings())
    try:
        await service.cancel_by_client(lead_id=lead_id, actor=current_user, reason=reason)
    except Exception as exc:
        await message.answer(str(exc))
        return

    await state.set_state(None)
    repo = LeadRepository(session)
    lead = await repo.get(lead_id)
    await pop(state)  # leave cancel_reason
    stack = await get_stack(state)
    if lead is not None:
        screen = render_my_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=message.bot,
            chat_id=message.chat.id,
            state=state,
            screen=screen,
        )
    await message.answer("✅ Причина сохранена. Заявка отменена.")
