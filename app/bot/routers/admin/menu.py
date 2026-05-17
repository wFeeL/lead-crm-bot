from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.screens.admin_assign_list import (
    ADMIN_ASSIGN_LIST_SCREEN_ID,
    AdminAssignCallback,
    render_admin_assign_list,
)
from app.bot.screens.admin_close_reason import (
    ADMIN_CLOSE_REASON_SCREEN_ID,
    AdminCloseReasonCallback,
    render_admin_close_reason,
)
from app.bot.screens.admin_comment_prompt import (
    ADMIN_COMMENT_PROMPT_SCREEN_ID,
    render_admin_comment_prompt,
)
from app.bot.screens.admin_lead_detail import (
    ADMIN_LEAD_DETAIL_SCREEN_ID,
    AdminDetailCallback,
    render_admin_lead_detail,
)
from app.bot.screens.admin_lead_list import (
    ADMIN_LEAD_LIST_SCREEN_ID,
    AdminLeadListCallback,
    render_admin_lead_list,
)
from app.bot.screens.admin_menu import (
    ADMIN_MENU_SCREEN_ID,
    AdminMenuCallback,
    render_admin_menu,
)
from app.bot.states.admin_flow import AdminFlowState
from app.bot.ui.navigation import clear_root_message_id, get_stack, go_home, pop, push
from app.bot.ui.render import render_screen
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import is_admin
from app.db.models.user import User
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.services.content import ContentService
from app.services.leads import LeadService
from app.services.notifications import NotificationService

router = Router(name="admin_menu")


def _is_admin_user(current_user, settings) -> bool:
    return is_admin(current_user.telegram_id, settings)


async def _render_admin_menu(*, bot, chat_id, state, session, content, settings):
    repo = LeadRepository(session)
    counts = await repo.status_counts()
    hot = await repo.hot_count()
    await push(state, ADMIN_MENU_SCREEN_ID)
    screen = render_admin_menu(
        content=content,
        status_counts=counts,
        hot_count=hot,
        company_name=content.brand.company_name,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


@router.message(Command("admin"))
async def admin_command(
    message: Message,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await message.answer("Недостаточно прав.")
        return
    await clear_root_message_id(state)
    await go_home(state)
    await pop(state)  # remove main_menu from stack, we want admin_menu as root
    await _render_admin_menu(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        session=session,
        content=content,
        settings=settings,
    )


@router.callback_query(AdminMenuCallback.filter())
async def on_admin_menu_action(
    callback: CallbackQuery,
    callback_data: AdminMenuCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    if callback_data.action == "csv":
        service = LeadService(session, settings)
        csv = await service.export_csv()
        await callback.message.answer_document(
            BufferedInputFile(csv.encode("utf-8-sig"), filename="leads.csv"),
            caption="CSV-выгрузка",
        )
        await callback.answer()
        return

    if callback_data.action == "stats":
        service = LeadService(session, settings)
        stats = await service.daily_stats()
        text = (
            f"📊 Статистика дня ({stats.date})\n\n"
            f"🆕 Новых: {stats.new}\n📞 Связались: —\n"
            f"🛠 В работе: {stats.in_progress}\n⏳ Ждут: {stats.waiting}\n"
            f"✅ Завершено: {stats.done}\n"
            f"❌ Отклонено: {stats.rejected}\n🚫 Отменено: {stats.cancelled}\n\n"
            f"Топ-категория: {stats.top_category or '—'}"
        )
        await callback.message.answer(text)
        await callback.answer()
        return

    # All other actions are filtered lead lists.
    filter_label = {
        "new": "🆕 Новые",
        "contacted": "📞 Связались",
        "in_progress": "🛠 В работе",
        "waiting": "⏳ Ждут клиента",
        "hot": "🔥 Срочные",
        "all": "📋 Все заявки",
    }.get(callback_data.action, "📋 Заявки")

    is_hot = callback_data.action == "hot"
    status_filter = None if callback_data.action in ("all", "hot") else callback_data.action

    await _show_lead_list(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        content=content,
        session=session,
        status=status_filter,
        hot=is_hot,
        page=1,
        filter_label=filter_label,
    )
    await callback.answer()


async def _show_lead_list(  # noqa: PLR0913
    *, bot, chat_id, state, content, session, status, hot, page, filter_label
):
    repo = LeadRepository(session)
    page_size = content.config.ui.page_size_admin
    leads = await repo.list_by_filter(
        status=status,
        hot=hot,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    total = await repo.count_by_filter(status=status, hot=hot)
    await push(state, ADMIN_LEAD_LIST_SCREEN_ID)
    # Stash filter in FSM data for pagination roundtrips.
    await state.update_data(admin_filter={"status": status, "hot": hot, "label": filter_label})
    stack = await get_stack(state)
    screen = render_admin_lead_list(
        content=content,
        leads=leads,
        page=page,
        total=total,
        page_size=page_size,
        filter_label=filter_label,
        stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


@router.callback_query(AdminLeadListCallback.filter())
async def on_admin_list_action(
    callback: CallbackQuery,
    callback_data: AdminLeadListCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    if callback_data.action == "page":
        data = await state.get_data()
        af = data.get("admin_filter") or {}
        await _show_lead_list(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            content=content,
            session=session,
            status=af.get("status"),
            hot=af.get("hot", False),
            page=callback_data.page,
            filter_label=af.get("label", "Заявки"),
        )
    elif callback_data.action == "open":
        repo = LeadRepository(session)
        lead = await repo.get(callback_data.lead_id)
        if lead is None:
            await callback.answer("Не найдено.", show_alert=True)
            return
        await push(state, ADMIN_LEAD_DETAIL_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
    await callback.answer()


@router.callback_query(AdminDetailCallback.filter())
async def on_admin_detail_action(
    callback: CallbackQuery,
    callback_data: AdminDetailCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    repo = LeadRepository(session)
    service = LeadService(session, settings)

    if callback_data.action == "set_status":
        target = callback_data.value
        if target in ("rejected", "done"):
            # Push close-reason screen.
            await push(state, ADMIN_CLOSE_REASON_SCREEN_ID)
            await state.update_data(
                admin_pending_status=target,
                admin_pending_lead=callback_data.lead_id,
            )
            stack = await get_stack(state)
            screen = render_admin_close_reason(
                content=content,
                lead_id=callback_data.lead_id,
                target_status=target,
                stack=stack,
            )
            await render_screen(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                state=state,
                screen=screen,
            )
            await callback.answer()
            return
        # Non-terminal status change.
        try:
            lead = await service.change_status(
                lead_id=callback_data.lead_id,
                status=target,
                actor=current_user,
            )
        except AppError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        # Optionally notify client of status change.
        await NotificationService(callback.bot, settings).notify_client_status(lead)
        # Re-render detail.
        stack = await get_stack(state)
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer("Статус изменён.")
        return

    if callback_data.action == "set_priority":
        try:
            lead = await service.set_priority(
                lead_id=callback_data.lead_id,
                priority=callback_data.value,
                actor=current_user,
            )
        except AppError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        stack = await get_stack(state)
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer("Приоритет обновлён.")
        return

    if callback_data.action in ("comment_internal", "comment_reply"):
        is_internal = callback_data.action == "comment_internal"
        lead = await repo.get(callback_data.lead_id)
        if lead is None:
            await callback.answer("Не найдено.", show_alert=True)
            return
        state_target = (
            AdminFlowState.writing_internal_comment
            if is_internal
            else AdminFlowState.writing_client_reply
        )
        await state.set_state(state_target)
        await state.update_data(admin_comment_lead_id=callback_data.lead_id)
        await push(state, ADMIN_COMMENT_PROMPT_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_admin_comment_prompt(
            content=content,
            lead_public_id=lead.public_id,
            is_internal=is_internal,
            stack=stack,
        )
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer()
        return

    if callback_data.action == "assign_me":
        try:
            lead = await service.reassign(
                lead_id=callback_data.lead_id,
                new_admin=current_user,
                actor=current_user,
            )
        except AppError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        stack = await get_stack(state)
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer("Назначено на вас.")
        return

    if callback_data.action == "assign":
        user_repo = UserRepository(session)
        admins = await user_repo.list_admins()
        await push(state, ADMIN_ASSIGN_LIST_SCREEN_ID)
        stack = await get_stack(state)
        lead = await repo.get(callback_data.lead_id)
        page_size = content.config.ui.page_size_admin
        screen = render_admin_assign_list(
            content=content,
            lead_id=callback_data.lead_id,
            current_admin_id=lead.assigned_admin_id if lead else None,
            admins=admins[:page_size],
            page=1,
            total=len(admins),
            page_size=page_size,
            stack=stack,
        )
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer()
        return


@router.callback_query(AdminCloseReasonCallback.filter())
async def on_close_reason_action(
    callback: CallbackQuery,
    callback_data: AdminCloseReasonCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    service = LeadService(session, settings)

    if callback_data.action == "custom":
        await state.set_state(AdminFlowState.writing_close_reason)
        await state.update_data(
            admin_pending_status=callback_data.target_status,
            admin_pending_lead=callback_data.lead_id,
        )
        await callback.message.answer("Напишите причину одним сообщением.")
        await callback.answer()
        return

    reason: str | None = None
    if callback_data.action == "pick":
        reasons = (
            content.texts.close_reasons.rejected
            if callback_data.target_status == "rejected"
            else content.texts.close_reasons.done
        )
        if callback_data.index < 0 or callback_data.index >= len(reasons):
            await callback.answer("Ошибка.", show_alert=True)
            return
        reason = reasons[callback_data.index]
    # action == "skip" → reason stays None (only allowed for DONE; rejected requires reason)

    if callback_data.target_status == "rejected" and reason is None:
        await callback.answer("Причина отказа обязательна.", show_alert=True)
        return

    try:
        lead = await service.change_status(
            lead_id=callback_data.lead_id,
            status=callback_data.target_status,
            actor=current_user,
            reason=reason,
        )
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await NotificationService(callback.bot, settings).notify_client_status(lead)
    # Pop close_reason screen, re-render detail.
    await pop(state)
    repo = LeadRepository(session)
    lead = await repo.get(callback_data.lead_id)
    stack = await get_stack(state)
    if lead is not None:
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
    await callback.answer("Статус изменён.")


@router.message(StateFilter(AdminFlowState.writing_close_reason))
async def on_custom_close_reason(
    message: Message,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, напишите причину.")
        return
    data = await state.get_data()
    target_status = data.get("admin_pending_status")
    lead_id = data.get("admin_pending_lead")
    if not target_status or not lead_id:
        await message.answer("Ошибка. Начните заново.")
        await state.set_state(None)
        return
    service = LeadService(session, get_settings())
    try:
        lead = await service.change_status(
            lead_id=lead_id,
            status=target_status,
            actor=current_user,
            reason=text,
        )
    except AppError as exc:
        await message.answer(str(exc))
        return
    await NotificationService(message.bot, get_settings()).notify_client_status(lead)
    await state.set_state(None)
    # Re-render detail.
    repo = LeadRepository(session)
    lead = await repo.get(lead_id)
    await pop(state)  # leave close_reason screen
    stack = await get_stack(state)
    if lead is not None:
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=message.bot,
            chat_id=message.chat.id,
            state=state,
            screen=screen,
        )
    await message.answer("✅ Готово.")


@router.callback_query(AdminAssignCallback.filter())
async def on_assign_action(
    callback: CallbackQuery,
    callback_data: AdminAssignCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    service = LeadService(session, settings)
    user_repo = UserRepository(session)
    repo = LeadRepository(session)

    if callback_data.action == "page":
        admins = await user_repo.list_admins()
        page_size = content.config.ui.page_size_admin
        offset = (callback_data.page - 1) * page_size
        slice_ = admins[offset : offset + page_size]
        lead = await repo.get(callback_data.lead_id)
        stack = await get_stack(state)
        screen = render_admin_assign_list(
            content=content,
            lead_id=callback_data.lead_id,
            current_admin_id=lead.assigned_admin_id if lead else None,
            admins=slice_,
            page=callback_data.page,
            total=len(admins),
            page_size=page_size,
            stack=stack,
        )
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer()
        return

    if callback_data.action == "unassign":
        new_admin = None
    else:  # pick
        result = await session.execute(select(User).where(User.id == callback_data.admin_id))
        new_admin = result.scalar_one_or_none()
        if new_admin is None:
            await callback.answer("Админ не найден.", show_alert=True)
            return

    try:
        lead = await service.reassign(
            lead_id=callback_data.lead_id,
            new_admin=new_admin,
            actor=current_user,
        )
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    # Notify new admin (if not self-assign).
    if new_admin is not None and new_admin.id != current_user.id:
        try:
            text = f"🔔 На вас назначена заявка №{lead.public_id}"
            await callback.bot.send_message(chat_id=new_admin.telegram_id, text=text)
        except Exception:
            pass

    # Pop assign_list, re-render detail.
    await pop(state)
    stack = await get_stack(state)
    screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
    await render_screen(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        screen=screen,
    )
    await callback.answer("Назначено.")


@router.message(StateFilter(AdminFlowState.writing_internal_comment))
@router.message(StateFilter(AdminFlowState.writing_client_reply))
async def on_admin_comment_text(
    message: Message,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    text = (message.text or "").strip()
    if not text:
        await message.answer("Комментарий не может быть пустым.")
        return
    if len(text) > 4000:
        await message.answer("Слишком длинный. Максимум 4000.")
        return
    data = await state.get_data()
    lead_id = data.get("admin_comment_lead_id")
    if not lead_id:
        await state.set_state(None)
        return
    is_internal = (await state.get_state()) == AdminFlowState.writing_internal_comment.state
    service = LeadService(session, settings)
    try:
        lead = await service.add_comment(
            lead_id=int(lead_id),
            admin=current_user,
            text=text,
            is_internal=is_internal,
        )
    except AppError as exc:
        await message.answer(str(exc))
        return

    if not is_internal:
        await NotificationService(message.bot, settings).notify_client_comment(lead, text)

    await state.set_state(None)
    await pop(state)  # leave comment_prompt screen
    stack = await get_stack(state)
    screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
    await render_screen(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        screen=screen,
    )
    await message.answer("✅ Сохранено.")
