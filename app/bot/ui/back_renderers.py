"""Concrete back-renderers for every screen the user can stack onto.

Each renderer:
- reads any context it needs from FSM data (``admin_filter``, current lead id,
  wizard answers, etc.) or from the DB via the session;
- re-renders the screen as the new root (``pop`` already adjusted the nav stack
  before we got here, so we MUST NOT ``push`` again);
- adjusts the FSM state where the screen owns a state (wizard back rewinds the
  user back into the right FSM state instead of leaving them mid-wizard with
  the wrong UI).

Call :func:`register_all` once at startup to install everything.
"""

from __future__ import annotations

from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.screens.admin_assign_list import (
    ADMIN_ASSIGN_LIST_SCREEN_ID,
    render_admin_assign_list,
)
from app.bot.screens.admin_close_reason import (
    ADMIN_CLOSE_REASON_SCREEN_ID,
    render_admin_close_reason,
)
from app.bot.screens.admin_comment_prompt import (
    ADMIN_COMMENT_PROMPT_SCREEN_ID,
    render_admin_comment_prompt,
)
from app.bot.screens.admin_lead_delete_confirm import (
    ADMIN_LEAD_DELETE_CONFIRM_SCREEN_ID,
    render_admin_lead_delete_confirm,
)
from app.bot.screens.admin_lead_detail import (
    ADMIN_LEAD_DETAIL_SCREEN_ID,
    render_admin_lead_detail,
)
from app.bot.screens.admin_lead_list import (
    ADMIN_LEAD_LIST_SCREEN_ID,
    render_admin_lead_list,
)
from app.bot.screens.admin_lead_timeline import (
    ADMIN_LEAD_TIMELINE_SCREEN_ID,
    render_admin_lead_timeline,
)
from app.bot.screens.admin_menu import ADMIN_MENU_SCREEN_ID, render_admin_menu
from app.bot.screens.admin_period_picker import (
    ADMIN_PERIOD_PICKER_SCREEN_ID,
    render_admin_period_picker,
)
from app.bot.screens.admin_search_prompt import (
    ADMIN_SEARCH_PROMPT_SCREEN_ID,
    render_admin_search_prompt,
)
from app.bot.screens.admin_stats import ADMIN_STATS_SCREEN_ID, render_admin_stats
from app.bot.screens.cancel_reason import (
    MY_LEAD_CANCEL_REASON_SCREEN_ID,
    render_cancel_reason,
)
from app.bot.screens.faq import (
    FAQ_ANSWER_SCREEN_ID,
    FAQ_SCREEN_ID,
    render_faq,
    render_faq_answer,
)
from app.bot.screens.lead_category import (
    LEAD_CATEGORY_SCREEN_ID,
    render_lead_category,
)
from app.bot.screens.lead_confirm import (
    LEAD_CONFIRM_SCREEN_ID,
    render_lead_confirm,
)
from app.bot.screens.lead_contact import (
    LEAD_CONTACT_PROMPT_SCREEN_ID,
    send_contact_prompt,
)
from app.bot.screens.lead_edit_answers import (
    LEAD_EDIT_ANSWERS_SCREEN_ID,
    render_lead_edit_answers,
)
from app.bot.screens.lead_files import (
    LEAD_UPLOAD_FILES_SCREEN_ID,
    render_lead_upload_files,
)
from app.bot.screens.lead_question import (
    LEAD_QUESTION_SCREEN_ID,
    render_lead_question,
)
from app.bot.screens.main_menu import MAIN_MENU_SCREEN_ID, render_main_menu
from app.bot.screens.my_leads import (
    MY_LEAD_DETAIL_SCREEN_ID,
    MY_LEADS_SCREEN_ID,
    render_my_lead_detail,
    render_my_leads,
)
from app.bot.screens.support import (
    SUPPORT_SCREEN_ID,
    SUPPORT_WRITING_SCREEN_ID,
    render_support,
    render_support_writing,
)
from app.bot.states.lead import LeadFormState
from app.bot.ui.back_registry import register_back
from app.bot.ui.navigation import get_stack
from app.bot.ui.render import render_screen
from app.core.config import get_settings
from app.db.repositories.forms import FormRepository
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.services.leads import LeadService


async def _back_main_menu(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    repo = LeadRepository(session)
    leads_count = await repo.count_by_user(current_user.id)
    screen = render_main_menu(content=content, leads_count=leads_count)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_my_leads(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    repo = LeadRepository(session)
    page_size = content.config.ui.page_size_my_leads
    leads = await repo.list_by_user(current_user.id, limit=page_size, offset=0)
    total = await repo.count_by_user(current_user.id)
    stack = await get_stack(state)
    screen = render_my_leads(content=content, leads=leads, page=1, total=total, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_my_lead_detail(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    lead_id = data.get("my_current_lead_id")
    if lead_id is None:
        await _back_my_leads(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    repo = LeadRepository(session)
    lead = await repo.get(int(lead_id))
    if lead is None or lead.user_id != current_user.id:
        await _back_my_leads(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    stack = await get_stack(state)
    screen = render_my_lead_detail(content=content, lead=lead, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_faq(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    stack = await get_stack(state)
    screen = render_faq(content=content, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_support(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    stack = await get_stack(state)
    screen = render_support(content=content, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_menu(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    repo = LeadRepository(session)
    counts = await repo.status_counts()
    hot = await repo.hot_count()
    screen = render_admin_menu(
        content=content,
        status_counts=counts,
        hot_count=hot,
        company_name=content.brand.company_name,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_search_prompt(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    stack = await get_stack(state)
    screen = render_admin_search_prompt(stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_period_picker(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    current_period = (data.get("admin_filter") or {}).get("period")
    stack = await get_stack(state)
    screen = render_admin_period_picker(current_period=current_period, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_stats(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    service = LeadService(session, get_settings())
    stats = await service.daily_stats()
    stack = await get_stack(state)
    screen = render_admin_stats(stats=stats, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_lead_list(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    af = data.get("admin_filter") or {}
    status = af.get("status")
    hot = bool(af.get("hot", False))
    label = af.get("label", "📋 Заявки")
    repo = LeadRepository(session)
    page_size = content.config.ui.page_size_admin
    leads = await repo.list_by_filter(status=status, hot=hot, limit=page_size, offset=0)
    total = await repo.count_by_filter(status=status, hot=hot)
    stack = await get_stack(state)
    screen = render_admin_lead_list(
        content=content,
        leads=leads,
        page=1,
        total=total,
        page_size=page_size,
        filter_label=label,
        stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_lead_detail(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    lead_id = data.get("admin_current_lead_id")
    if lead_id is None:
        await _back_admin_lead_list(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    repo = LeadRepository(session)
    lead = await repo.get(int(lead_id))
    if lead is None:
        await _back_admin_lead_list(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    stack = await get_stack(state)
    screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_lead_timeline(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    lead_id = data.get("admin_current_lead_id")
    if lead_id is None:
        await _back_admin_lead_list(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    repo = LeadRepository(session)
    lead = await repo.get(int(lead_id))
    if lead is None:
        await _back_admin_lead_list(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    events = await repo.list_events(lead_id=lead.id)
    stack = await get_stack(state)
    screen = render_admin_lead_timeline(
        content=content,
        public_id=str(lead.public_id),
        events=events,
        stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_lead_delete_confirm(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    lead_id = data.get("admin_current_lead_id")
    if lead_id is None:
        await _back_admin_lead_list(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    repo = LeadRepository(session)
    lead = await repo.get(int(lead_id))
    if lead is None:
        await _back_admin_lead_list(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    stack = await get_stack(state)
    screen = render_admin_lead_delete_confirm(
        public_id=str(lead.public_id), lead_id=lead.id, stack=stack
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_assign_list(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    lead_id = data.get("admin_current_lead_id")
    if lead_id is None:
        await _back_admin_lead_list(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    repo = LeadRepository(session)
    lead = await repo.get(int(lead_id))
    if lead is None:
        return
    user_repo = UserRepository(session)
    admins = await user_repo.list_admins()
    page_size = content.config.ui.page_size_admin
    stack = await get_stack(state)
    screen = render_admin_assign_list(
        content=content,
        lead_id=int(lead_id),
        current_admin_id=lead.assigned_admin_id if lead else None,
        admins=admins[:page_size],
        page=1,
        total=len(admins),
        page_size=page_size,
        stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_lead_category(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    """Returning to the category screen resets the wizard to its first step."""
    repo = FormRepository(session)
    categories = await repo.list_categories()
    # Reset wizard state.
    await state.set_state(LeadFormState.choosing_category)
    await state.update_data(questions=[], question_index=0, answers=[], files=[])
    stack = await get_stack(state)
    screen = render_lead_category(content=content, categories=categories, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_lead_question(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    """Back into the question step: drop the last answer and re-show that question."""
    data = await state.get_data()
    questions = data.get("questions") or []
    answers = data.get("answers") or []
    if not questions:
        await _back_lead_category(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    if answers:
        answers.pop()
    index = max(0, min(len(answers), len(questions) - 1))
    await state.update_data(answers=answers, question_index=index)
    await state.set_state(LeadFormState.answering_questions)
    stack = await get_stack(state)
    screen = render_lead_question(
        content=content,
        question=questions[index],
        index=index,
        total=len(questions),
        stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_lead_upload_files(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    files = data.get("files") or []
    settings = get_settings()
    await state.set_state(LeadFormState.uploading_files)
    stack = await get_stack(state)
    screen = render_lead_upload_files(
        content=content,
        files=files,
        max_files=settings.max_files_per_lead,
        stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_lead_contact_prompt(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    await state.set_state(LeadFormState.entering_contact)
    await send_contact_prompt(bot=bot, chat_id=chat_id, state=state)


async def _back_lead_edit_answers(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    """Return to the edit-answers list while keeping all in-progress edits."""
    await state.set_state(LeadFormState.editing_one_answer)
    data = await state.get_data()
    stack = await get_stack(state)
    screen = render_lead_edit_answers(content=content, draft=data, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_faq_answer(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    """Backing out of a FAQ answer takes the user to the FAQ list, not main menu."""
    data = await state.get_data()
    index = data.get("faq_current_index")
    if index is None:
        await _back_faq(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    stack = await get_stack(state)
    try:
        screen = render_faq_answer(content=content, index=int(index), stack=stack)
    except IndexError:
        # FAQ shrank between sessions — fall back to the list.
        await _back_faq(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_support_writing(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    stack = await get_stack(state)
    screen = render_support_writing(content=content, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_my_lead_cancel_reason(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    lead_id = data.get("cancel_target_lead_id") or data.get("my_current_lead_id")
    if lead_id is None:
        await _back_my_leads(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    stack = await get_stack(state)
    screen = render_cancel_reason(content=content, lead_id=int(lead_id), stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_close_reason(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    lead_id = data.get("admin_pending_lead") or data.get("admin_current_lead_id")
    target_status = data.get("admin_pending_status")
    if lead_id is None or target_status is None:
        await _back_admin_lead_detail(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    stack = await get_stack(state)
    screen = render_admin_close_reason(
        content=content,
        lead_id=int(lead_id),
        target_status=target_status,
        stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_admin_comment_prompt(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    from app.bot.states.admin_flow import AdminFlowState

    data = await state.get_data()
    lead_id = data.get("admin_comment_lead_id") or data.get("admin_current_lead_id")
    if lead_id is None:
        await _back_admin_lead_detail(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    repo = LeadRepository(session)
    lead = await repo.get(int(lead_id))
    if lead is None:
        await _back_admin_lead_detail(
            bot=bot,
            chat_id=chat_id,
            state=state,
            session=session,
            content=content,
            current_user=current_user,
        )
        return
    # Default to internal — we lost the original flag, but the FSM state tells us.
    current_state = await state.get_state()
    is_internal = current_state != AdminFlowState.writing_client_reply.state
    stack = await get_stack(state)
    screen = render_admin_comment_prompt(
        content=content,
        lead_public_id=str(lead.public_id),
        is_internal=is_internal,
        stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


async def _back_lead_confirm(
    *, bot, chat_id: int, state: FSMContext, session: AsyncSession, content, current_user
) -> None:
    data = await state.get_data()
    await state.set_state(LeadFormState.confirming)
    stack = await get_stack(state)
    screen = render_lead_confirm(content=content, draft=data, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


def register_all() -> None:
    """Install every back-renderer. Safe to call multiple times (overwrites)."""
    register_back(MAIN_MENU_SCREEN_ID, _back_main_menu)
    register_back(MY_LEADS_SCREEN_ID, _back_my_leads)
    register_back(MY_LEAD_DETAIL_SCREEN_ID, _back_my_lead_detail)
    register_back(FAQ_SCREEN_ID, _back_faq)
    register_back(SUPPORT_SCREEN_ID, _back_support)
    register_back(ADMIN_MENU_SCREEN_ID, _back_admin_menu)
    register_back(ADMIN_STATS_SCREEN_ID, _back_admin_stats)
    register_back(ADMIN_SEARCH_PROMPT_SCREEN_ID, _back_admin_search_prompt)
    register_back(ADMIN_PERIOD_PICKER_SCREEN_ID, _back_admin_period_picker)
    register_back(ADMIN_LEAD_LIST_SCREEN_ID, _back_admin_lead_list)
    register_back(ADMIN_LEAD_DETAIL_SCREEN_ID, _back_admin_lead_detail)
    register_back(ADMIN_ASSIGN_LIST_SCREEN_ID, _back_admin_assign_list)
    register_back(ADMIN_LEAD_DELETE_CONFIRM_SCREEN_ID, _back_admin_lead_delete_confirm)
    register_back(ADMIN_LEAD_TIMELINE_SCREEN_ID, _back_admin_lead_timeline)
    register_back(LEAD_CATEGORY_SCREEN_ID, _back_lead_category)
    register_back(LEAD_QUESTION_SCREEN_ID, _back_lead_question)
    register_back(LEAD_UPLOAD_FILES_SCREEN_ID, _back_lead_upload_files)
    register_back(LEAD_CONTACT_PROMPT_SCREEN_ID, _back_lead_contact_prompt)
    register_back(LEAD_CONFIRM_SCREEN_ID, _back_lead_confirm)
    register_back(LEAD_EDIT_ANSWERS_SCREEN_ID, _back_lead_edit_answers)
    # Previously-missing back-renderers — without these, ⬅ Назад dropped the
    # user out of mid-flow back to MAIN_MENU.
    register_back(FAQ_ANSWER_SCREEN_ID, _back_faq_answer)
    register_back(SUPPORT_WRITING_SCREEN_ID, _back_support_writing)
    register_back(MY_LEAD_CANCEL_REASON_SCREEN_ID, _back_my_lead_cancel_reason)
    register_back(ADMIN_CLOSE_REASON_SCREEN_ID, _back_admin_close_reason)
    register_back(ADMIN_COMMENT_PROMPT_SCREEN_ID, _back_admin_comment_prompt)
