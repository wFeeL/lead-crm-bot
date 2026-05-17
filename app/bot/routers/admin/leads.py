from datetime import date

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.builders import (
    AdminLeadCallback,
    AdminMenuCallback,
    AdminStatusCallback,
    admin_comment_keyboard,
    admin_lead_keyboard,
    admin_menu_keyboard,
)
from app.bot.states.lead import AdminCommentState
from app.bot.utils import remove_inline_keyboard, replace_message_text
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.security import is_admin
from app.db.models.user import User
from app.services.formatting import format_lead_summary
from app.services.leads import LeadService
from app.services.notifications import NotificationService

router = Router(name="admin_leads")


async def _require_admin(message_or_callback, current_user: User, settings: Settings) -> bool:
    if is_admin(current_user.telegram_id, settings):
        return True
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer("Недостаточно прав.", show_alert=True)
    else:
        await message_or_callback.answer("Недостаточно прав.")
    return False


@router.message(Command("admin"))
async def admin_panel(message: Message, current_user: User) -> None:
    settings = get_settings()
    if not await _require_admin(message, current_user, settings):
        return
    await message.answer(
        "Админ-панель\n\n"
        "Команды:\n"
        "/new — новые заявки\n"
        "/leads — все заявки\n"
        "/leads_user <telegram_id|@username> — фильтр по пользователю\n"
        "/leads_date <YYYY-MM-DD> — фильтр по дате\n"
        "/export — CSV-выгрузка",
        reply_markup=admin_menu_keyboard(),
    )


async def _send_lead_list(
    target: Message,
    *,
    session: AsyncSession,
    settings: Settings,
    status: str | None = None,
    user_query: str | None = None,
    created_date: date | None = None,
    edit: bool = False,
) -> None:
    service = LeadService(session, settings)
    leads = await service.list_leads(
        status=status,
        user_query=user_query,
        date_from=created_date,
        date_to=created_date,
        limit=10,
    )
    title = "Заявки"
    if status:
        title += f" / {status}"
    if user_query:
        title += f" / пользователь: {user_query}"
    if created_date:
        title += f" / дата: {created_date.isoformat()}"
    if not leads:
        text = f"{title}\n\nНичего не найдено."
        if edit:
            await replace_message_text(target, text, reply_markup=admin_menu_keyboard())
        else:
            await target.answer(text, reply_markup=admin_menu_keyboard())
        return
    text = f"{title}\n\nНайдено: {len(leads)}. Открывайте карточки ниже."
    if edit:
        await replace_message_text(target, text, reply_markup=admin_menu_keyboard())
    else:
        await target.answer(text, reply_markup=admin_menu_keyboard())
    for lead in leads:
        await target.answer(format_lead_summary(lead), reply_markup=admin_lead_keyboard(lead))


@router.message(Command("new"))
async def new_leads(message: Message, session: AsyncSession, current_user: User) -> None:
    settings = get_settings()
    if not await _require_admin(message, current_user, settings):
        return
    await _send_lead_list(message, session=session, settings=settings, status="new")


@router.message(Command("leads"))
async def all_leads(message: Message, session: AsyncSession, current_user: User) -> None:
    settings = get_settings()
    if not await _require_admin(message, current_user, settings):
        return
    await _send_lead_list(message, session=session, settings=settings)


@router.message(Command("leads_user"))
async def leads_by_user(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    current_user: User,
) -> None:
    settings = get_settings()
    if not await _require_admin(message, current_user, settings):
        return
    user_query = (command.args or "").strip()
    if not user_query:
        await message.answer(
            "Укажите пользователя: /leads_user 416966184 или /leads_user @username"
        )
        return
    await _send_lead_list(message, session=session, settings=settings, user_query=user_query)


@router.message(Command("leads_date"))
async def leads_by_date(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    current_user: User,
) -> None:
    settings = get_settings()
    if not await _require_admin(message, current_user, settings):
        return
    raw_date = (command.args or "").strip()
    try:
        created_date = date.fromisoformat(raw_date)
    except ValueError:
        await message.answer("Укажите дату в формате YYYY-MM-DD: /leads_date 2026-05-17")
        return
    await _send_lead_list(message, session=session, settings=settings, created_date=created_date)


@router.callback_query(AdminMenuCallback.filter(F.action == "menu"))
async def admin_menu_callback(callback: CallbackQuery, current_user: User) -> None:
    settings = get_settings()
    if not await _require_admin(callback, current_user, settings):
        return
    await replace_message_text(
        callback.message,
        "Админ-панель",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(AdminMenuCallback.filter(F.action == "list"))
async def admin_list_callback(
    callback: CallbackQuery,
    callback_data: AdminMenuCallback,
    session: AsyncSession,
    current_user: User,
) -> None:
    settings = get_settings()
    if not await _require_admin(callback, current_user, settings):
        return
    await _send_lead_list(
        callback.message,
        session=session,
        settings=settings,
        status=callback_data.status or None,
        edit=True,
    )
    await callback.answer()


@router.callback_query(AdminMenuCallback.filter(F.action == "export"))
async def admin_export_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
) -> None:
    settings = get_settings()
    if not await _require_admin(callback, current_user, settings):
        return
    service = LeadService(session, settings)
    csv_payload = await service.export_csv()
    await callback.message.answer_document(
        BufferedInputFile(csv_payload.encode("utf-8-sig"), filename="leads.csv"),
        caption="CSV-выгрузка заявок",
    )
    await callback.answer()


@router.message(Command("export"))
async def export_leads(message: Message, session: AsyncSession, current_user: User) -> None:
    settings = get_settings()
    if not await _require_admin(message, current_user, settings):
        return
    service = LeadService(session, settings)
    csv_payload = await service.export_csv()
    await message.answer_document(
        BufferedInputFile(csv_payload.encode("utf-8-sig"), filename="leads.csv"),
        caption="CSV-выгрузка заявок",
    )


@router.callback_query(AdminLeadCallback.filter(F.action == "detail"))
async def lead_detail(
    callback: CallbackQuery,
    callback_data: AdminLeadCallback,
    session: AsyncSession,
    current_user: User,
) -> None:
    settings = get_settings()
    if not await _require_admin(callback, current_user, settings):
        return
    service = LeadService(session, settings)
    try:
        lead = await service.get_lead(callback_data.lead_id)
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await replace_message_text(
        callback.message,
        format_lead_summary(lead),
        reply_markup=admin_lead_keyboard(lead),
    )
    await callback.answer()


@router.callback_query(AdminLeadCallback.filter(F.action == "take"))
async def take_lead(
    callback: CallbackQuery,
    callback_data: AdminLeadCallback,
    session: AsyncSession,
    current_user: User,
) -> None:
    settings = get_settings()
    if not await _require_admin(callback, current_user, settings):
        return
    service = LeadService(session, settings)
    try:
        lead = await service.assign_to_admin(lead_id=callback_data.lead_id, admin=current_user)
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await replace_message_text(
        callback.message,
        format_lead_summary(lead),
        reply_markup=admin_lead_keyboard(lead),
    )
    await callback.answer(f"Заявка {lead.public_id or lead.id} назначена на вас.")


@router.callback_query(AdminLeadCallback.filter(F.action.in_({"comment", "public_comment"})))
async def start_comment(
    callback: CallbackQuery,
    callback_data: AdminLeadCallback,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
) -> None:
    settings = get_settings()
    if not await _require_admin(callback, current_user, settings):
        return
    service = LeadService(session, settings)
    try:
        lead = await service.get_lead(callback_data.lead_id)
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    is_internal = callback_data.action == "comment"
    await state.set_state(AdminCommentState.waiting_for_comment)
    await state.update_data(comment_lead_id=callback_data.lead_id, comment_is_internal=is_internal)
    comment_type = "внутренний комментарий" if is_internal else "ответ клиенту"
    await callback.message.answer(
        f"Напишите {comment_type} к заявке {lead.public_id or lead.id}.",
        reply_markup=admin_comment_keyboard(callback_data.lead_id),
    )
    await callback.answer()


@router.callback_query(
    AdminCommentState.waiting_for_comment,
    AdminLeadCallback.filter(F.action == "cancel_comment"),
)
async def cancel_comment(callback: CallbackQuery, state: FSMContext, current_user: User) -> None:
    settings = get_settings()
    if not await _require_admin(callback, current_user, settings):
        return
    await state.clear()
    await remove_inline_keyboard(callback.message)
    await callback.answer("Комментарий отменен.")


@router.callback_query(AdminLeadCallback.filter(F.action == "cancel_comment"))
async def stale_cancel_comment(callback: CallbackQuery, current_user: User) -> None:
    settings = get_settings()
    if not await _require_admin(callback, current_user, settings):
        return
    await remove_inline_keyboard(callback.message)
    await callback.answer("Это действие уже неактуально.", show_alert=True)


@router.message(AdminCommentState.waiting_for_comment)
async def save_comment(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
) -> None:
    settings = get_settings()
    if not await _require_admin(message, current_user, settings):
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Комментарий не может быть пустым.")
        return
    if len(text) > 4000:
        await message.answer("Комментарий слишком длинный. Максимум 4000 символов.")
        return
    data = await state.get_data()
    service = LeadService(session, settings)
    lead_id = int(data["comment_lead_id"])
    is_internal = bool(data.get("comment_is_internal", True))
    try:
        lead = await service.add_comment(
            lead_id=lead_id,
            admin=current_user,
            text=text,
            is_internal=is_internal,
        )
    except AppError as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    if not is_internal:
        await NotificationService(message.bot, settings).notify_client_comment(lead, text)
    await message.answer(
        "Комментарий добавлен." if is_internal else "Ответ клиенту добавлен.",
        reply_markup=admin_lead_keyboard(lead),
    )


@router.callback_query(AdminStatusCallback.filter())
async def change_status(
    callback: CallbackQuery,
    callback_data: AdminStatusCallback,
    session: AsyncSession,
    current_user: User,
) -> None:
    settings = get_settings()
    if not await _require_admin(callback, current_user, settings):
        return
    service = LeadService(session, settings)
    try:
        lead = await service.change_status(
            lead_id=callback_data.lead_id,
            status=callback_data.status,
            actor=current_user,
        )
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await NotificationService(callback.bot, settings).notify_client_status(lead)
    await replace_message_text(
        callback.message,
        format_lead_summary(lead),
        reply_markup=admin_lead_keyboard(lead),
    )
    await callback.answer("Статус изменен.")
