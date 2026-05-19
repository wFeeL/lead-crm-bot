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
from app.bot.screens.admin_lead_delete_confirm import (
    ADMIN_LEAD_DELETE_CONFIRM_SCREEN_ID,
    AdminLeadDeleteCallback,
    render_admin_lead_delete_confirm,
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
from app.bot.screens.admin_period_picker import (
    ADMIN_PERIOD_PICKER_SCREEN_ID,
    AdminPeriodCallback,
    render_admin_period_picker,
)
from app.bot.screens.admin_search_prompt import (
    ADMIN_SEARCH_PROMPT_SCREEN_ID,
    render_admin_search_prompt,
)
from app.bot.screens.admin_stats import ADMIN_STATS_SCREEN_ID, render_admin_stats
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
from app.services.period import period_label, resolve_period

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
        # Document delivery is its own message; the admin_menu root stays put,
        # so the admin can pick another action without needing a "back" button.
        await callback.message.answer_document(
            BufferedInputFile(csv.encode("utf-8-sig"), filename="leads.csv"),
            caption="📤 CSV-выгрузка готова. Меню админа выше — продолжайте работу там.",
        )
        await callback.answer()
        return

    if callback_data.action == "stats":
        service = LeadService(session, settings)
        stats = await service.daily_stats()
        # Render as a proper screen so the nav-footer back-button returns the
        # admin to the menu instead of leaving them with a dead-end message.
        await push(state, ADMIN_STATS_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_admin_stats(stats=stats, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer()
        return

    if callback_data.action == "search":
        # Drop any stale search query so the new prompt is fresh.
        await state.update_data(admin_search_query=None)
        await push(state, ADMIN_SEARCH_PROMPT_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_admin_search_prompt(stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer()
        return

    if callback_data.action == "period":
        data = await state.get_data()
        current_period = (data.get("admin_filter") or {}).get("period")
        await push(state, ADMIN_PERIOD_PICKER_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_admin_period_picker(current_period=current_period, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
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

    # Preserve the existing period filter across status switches.
    data = await state.get_data()
    period = (data.get("admin_filter") or {}).get("period")

    await _show_lead_list(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        content=content,
        session=session,
        status=status_filter,
        hot=is_hot,
        period=period,
        page=1,
        filter_label=filter_label,
    )
    await callback.answer()


def _label_with_period(base: str, period: str | None) -> str:
    """Append the period suffix to the list title (e.g. '🆕 Новые · Неделя')."""
    if period in (None, "all"):
        return base
    return f"{base} · {period_label(period)}"


async def _show_lead_list(  # noqa: PLR0913
    *,
    bot,
    chat_id,
    state,
    content,
    session,
    status,
    hot,
    period,
    page,
    filter_label,
):
    repo = LeadRepository(session)
    page_size = content.config.ui.page_size_admin
    date_from, date_to = resolve_period(period)
    leads = await repo.list_by_filter(
        status=status,
        hot=hot,
        date_from=date_from,
        date_to=date_to,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    total = await repo.count_by_filter(
        status=status,
        hot=hot,
        date_from=date_from,
        date_to=date_to,
    )
    await push(state, ADMIN_LEAD_LIST_SCREEN_ID)
    label = _label_with_period(filter_label, period)
    # Stash filter in FSM data for pagination roundtrips and back-renderers.
    await state.update_data(
        admin_filter={
            "status": status,
            "hot": hot,
            "period": period,
            "label": filter_label,  # base label without period suffix
        }
    )
    stack = await get_stack(state)
    screen = render_admin_lead_list(
        content=content,
        leads=leads,
        page=page,
        total=total,
        page_size=page_size,
        filter_label=label,
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
        if af.get("query"):
            # Search results paginate through the search results, not the regular filter.
            await _show_search_results(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                state=state,
                content=content,
                session=session,
                query=af["query"],
                page=callback_data.page,
            )
        else:
            await _show_lead_list(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                state=state,
                content=content,
                session=session,
                status=af.get("status"),
                hot=af.get("hot", False),
                period=af.get("period"),
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
        # Remember which lead the admin is currently viewing so the back-renderer
        # (admin_lead_detail) can re-fetch it when the user backs out of nested
        # screens like assignment list / close-reason / comment prompt.
        await state.update_data(admin_current_lead_id=lead.id)
        stack = await get_stack(state)
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        # Open the lead in a fresh message so the previous list stays scrollable.
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
            force_new=True,
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

    if callback_data.action == "delete":
        lead = await repo.get(callback_data.lead_id)
        if lead is None:
            await callback.answer("Не найдено.", show_alert=True)
            return
        await push(state, ADMIN_LEAD_DELETE_CONFIRM_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_admin_lead_delete_confirm(
            public_id=str(lead.public_id),
            lead_id=lead.id,
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


@router.callback_query(AdminLeadDeleteCallback.filter())
async def on_admin_lead_delete(
    callback: CallbackQuery,
    callback_data: AdminLeadDeleteCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    if callback_data.action == "cancel":
        # Pop confirmation, re-render the underlying detail screen.
        await pop(state)
        repo = LeadRepository(session)
        lead = await repo.get(callback_data.lead_id)
        if lead is not None:
            stack = await get_stack(state)
            screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
            await render_screen(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                state=state,
                screen=screen,
            )
        await callback.answer()
        return

    # action == "confirm" — perform soft-delete and bounce admin back to the list.
    service = LeadService(session, settings)
    try:
        await service.delete_lead(lead_id=callback_data.lead_id, actor=current_user)
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    # Drop both the confirmation and the detail from the nav stack — the lead
    # is gone, returning to it makes no sense. Then re-render the list filter
    # the admin came from.
    await pop(state)  # leave delete_confirm
    await pop(state)  # leave admin_lead_detail
    # Clear the cached current_lead_id so back-renderers don't re-fetch a deleted lead.
    data = await state.get_data()
    if "admin_current_lead_id" in data:
        await state.update_data(admin_current_lead_id=None)

    data = await state.get_data()
    af = data.get("admin_filter") or {}
    page_size = content.config.ui.page_size_admin
    repo = LeadRepository(session)
    leads = await repo.list_by_filter(
        status=af.get("status"),
        hot=bool(af.get("hot", False)),
        limit=page_size,
        offset=0,
    )
    total = await repo.count_by_filter(
        status=af.get("status"),
        hot=bool(af.get("hot", False)),
    )
    stack = await get_stack(state)
    from app.bot.screens.admin_lead_list import render_admin_lead_list

    screen = render_admin_lead_list(
        content=content,
        leads=leads,
        page=1,
        total=total,
        page_size=page_size,
        filter_label=af.get("label", "📋 Заявки"),
        stack=stack,
    )
    await render_screen(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        screen=screen,
    )
    await callback.answer("🗑 Заявка удалена.")


# ============= Search & period (Tier 2) =====================================


async def _show_search_results(
    *,
    bot,
    chat_id: int,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    query: str,
    page: int,
) -> None:
    repo = LeadRepository(session)
    page_size = content.config.ui.page_size_admin
    leads = await repo.search(query=query, limit=page_size, offset=(page - 1) * page_size)
    total = await repo.count_search(query=query)
    # admin_filter holds only the query for search mode; pagination + back-renderer
    # check af.get("query") to know we're in search mode.
    await state.update_data(
        admin_filter={
            "query": query,
            "label": f"🔎 Результаты: «{query}»",
        }
    )
    await push(state, ADMIN_LEAD_LIST_SCREEN_ID)
    stack = await get_stack(state)
    screen = render_admin_lead_list(
        content=content,
        leads=leads,
        page=page,
        total=total,
        page_size=page_size,
        filter_label=f"🔎 Результаты: «{query}»",
        stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


@router.message(StateFilter(AdminFlowState.searching))
async def on_admin_search_query(
    message: Message,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    """Admin typed a search query — run it and render results as a list."""
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        return
    query = (message.text or "").strip()
    if not query:
        await message.answer("Запрос пуст — отправьте номер, @username или № заявки.")
        return
    if len(query) > 100:
        await message.answer("Слишком длинный запрос. Сократите до 100 символов.")
        return
    await state.set_state(None)
    # Leave the prompt screen behind so back from the results returns to admin_menu.
    await pop(state)
    await _show_search_results(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        content=content,
        session=session,
        query=query,
        page=1,
    )


@router.callback_query(AdminPeriodCallback.filter())
async def on_admin_period_pick(
    callback: CallbackQuery,
    callback_data: AdminPeriodCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    # Persist the new period and bounce admin to a fresh "all leads" view filtered
    # by that period. The previous status/hot filter is reset — period acts as a
    # standalone slice, not a modifier on top of status.
    new_period = callback_data.period
    await pop(state)  # leave period_picker; next call will push admin_lead_list

    await _show_lead_list(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        content=content,
        session=session,
        status=None,
        hot=False,
        period=new_period,
        page=1,
        filter_label="📋 Все заявки",
    )
    await callback.answer(f"📅 {period_label(new_period)}")
