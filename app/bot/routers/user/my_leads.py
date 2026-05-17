from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.screens.my_leads import (
    MY_LEAD_DETAIL_SCREEN_ID,
    MY_LEADS_SCREEN_ID,
    MyLeadDetailCallback,
    MyLeadsCallback,
    render_my_lead_detail,
    render_my_leads,
)
from app.bot.ui.navigation import get_stack, push
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
        service = LeadService(session, get_settings())
        try:
            await service.cancel_by_client(lead_id=callback_data.lead_id, actor=current_user)
            await callback.answer("✅ Заявка отменена.")
        except Exception as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        # Re-render detail with new status.
        repo = LeadRepository(session)
        lead = await repo.get(callback_data.lead_id)
        if lead is None:
            await callback.answer()
            return
        stack = await get_stack(state)
        screen = render_my_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
    else:
        # Unhandled actions (e.g. literal "open" — currently dead) must still
        # acknowledge the callback to clear Telegram's spinner.
        await callback.answer()
