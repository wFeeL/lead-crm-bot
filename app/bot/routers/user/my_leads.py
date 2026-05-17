from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.builders import (
    MenuCallback,
    UserLeadCallback,
    main_menu_keyboard,
    user_lead_detail_keyboard,
    user_leads_keyboard,
)
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.models.user import User
from app.services.formatting import format_public_lead_line, format_user_lead_detail
from app.services.leads import LeadService

router = Router(name="user_my_leads")


@router.callback_query(MenuCallback.filter(F.action == "my_leads"))
async def my_leads(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    state: FSMContext,
) -> None:
    await state.clear()
    service = LeadService(session, get_settings())
    leads = await service.list_user_leads(current_user.id)
    if not leads:
        await callback.message.edit_text(
            "У вас пока нет заявок.",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return
    lines = "\n".join(format_public_lead_line(lead) for lead in leads)
    await callback.message.edit_text(
        f"Ваши заявки:\n\n{lines}\n\nВыберите заявку, чтобы открыть карточку.",
        reply_markup=user_leads_keyboard(leads) or main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(UserLeadCallback.filter(F.action == "detail"))
async def my_lead_detail(
    callback: CallbackQuery,
    callback_data: UserLeadCallback,
    session: AsyncSession,
    current_user: User,
) -> None:
    service = LeadService(session, get_settings())
    try:
        lead = await service.get_lead(callback_data.lead_id)
        if lead.user_id != current_user.id:
            await callback.answer("Заявка не найдена.", show_alert=True)
            return
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.message.edit_text(
        format_user_lead_detail(lead),
        reply_markup=user_lead_detail_keyboard(lead),
    )
    await callback.answer()


@router.callback_query(UserLeadCallback.filter(F.action == "back_to_list"))
async def back_to_my_leads(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
) -> None:
    service = LeadService(session, get_settings())
    leads = await service.list_user_leads(current_user.id)
    lines = "\n".join(format_public_lead_line(lead) for lead in leads)
    await callback.message.edit_text(
        f"Ваши заявки:\n\n{lines or 'Заявок нет.'}",
        reply_markup=user_leads_keyboard(leads) or main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(UserLeadCallback.filter(F.action == "cancel"))
async def cancel_my_lead(
    callback: CallbackQuery,
    callback_data: UserLeadCallback,
    session: AsyncSession,
    current_user: User,
) -> None:
    service = LeadService(session, get_settings())
    try:
        lead = await service.cancel_by_client(lead_id=callback_data.lead_id, actor=current_user)
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.message.edit_text(
        f"Заявка {lead.public_id or lead.id} отменена.\n\n{format_user_lead_detail(lead)}",
        reply_markup=user_lead_detail_keyboard(lead),
    )
    await callback.answer()
