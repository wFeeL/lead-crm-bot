"""Integration tests for the cancel-reason flow (Task 4.5)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.routers.user.my_leads import (
    handle_cancel_custom_reason,
    handle_cancel_reason,
    handle_lead_detail_action,
)
from app.bot.screens.cancel_reason import CancelReasonCallback
from app.bot.screens.my_leads import MyLeadDetailCallback
from app.bot.states.cancel import MyLeadCancelState
from app.bot.ui.navigation import get_stack
from app.core.config import Settings
from app.core.constants import LeadStatus
from app.db.repositories.forms import FormRepository
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.schemas.lead import LeadCreateInput
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from app.services.leads import LeadService
from sqlalchemy.ext.asyncio import AsyncSession

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"
_BUNDLE = ContentService.load(_CONTENT_DIR)


@pytest.fixture
def content():
    return ContentService(_BUNDLE)


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    fsm = FSMContext(storage=storage, key=key)
    await fsm.update_data(
        {"root_message_id": 999, "nav_stack": ["main_menu", "my_leads", "my_lead_detail"]}
    )
    return fsm


@pytest.fixture
async def current_user(session: AsyncSession, content):
    await ensure_seed_data(session, content.bundle)
    await session.commit()
    repo = UserRepository(session)
    return await repo.upsert_telegram_user(
        telegram_id=42,
        username="test_user",
        first_name="Test",
        last_name=None,
        is_admin=False,
    )


@pytest.fixture
async def new_lead(session: AsyncSession, current_user):
    category = await FormRepository(session).get_category_by_slug("other")
    service = LeadService(session, Settings(admin_ids=[999]))
    return await service.create_lead(
        LeadCreateInput(
            user_id=current_user.id,
            category_id=category.id,
            title=category.title,
            description="Cancel reason test",
            contact_name="Test",
            contact_phone="@test",
            contact_username="test_user",
        )
    )


def _callback(message_id=999):
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=message_id))
    callback = MagicMock()
    callback.bot = bot
    callback.message = MagicMock(chat=MagicMock(id=42), message_id=message_id)
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()
    return callback


# ─── Test 1: cancel pushes reason screen ───────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_action_pushes_reason_screen(
    content, state, session: AsyncSession, current_user, new_lead
):
    """MY_LEAD_DETAIL cancel action pushes cancel_reason screen, lead not yet cancelled."""
    callback = _callback()

    await handle_lead_detail_action(
        callback=callback,
        callback_data=MyLeadDetailCallback(action="cancel", lead_id=new_lead.id),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    callback.answer.assert_awaited()
    # Reason screen rendered.
    callback.bot.edit_message_text.assert_awaited_once()
    text = callback.bot.edit_message_text.await_args.kwargs["text"]
    assert "Отмена заявки" in text

    # Lead still NEW.
    lead = await LeadRepository(session).get(new_lead.id)
    assert lead.status == LeadStatus.NEW

    # Nav stack now has cancel_reason.
    stack = await get_stack(state)
    assert stack[-1] == "my_lead_cancel_reason"


# ─── Test 2: pick predefined reason cancels the lead ──────────────────────


@pytest.mark.asyncio
async def test_pick_predefined_reason_cancels_lead(
    content, state, session: AsyncSession, current_user, new_lead
):
    """Picking a predefined reason calls cancel_by_client and re-renders MY_LEAD_DETAIL."""
    # First push the cancel_reason screen into the stack.
    from app.bot.screens.cancel_reason import MY_LEAD_CANCEL_REASON_SCREEN_ID
    from app.bot.ui.navigation import push

    await push(state, MY_LEAD_CANCEL_REASON_SCREEN_ID)

    callback = _callback()

    # "Передумал" is index 0 in default texts.yaml close_reasons.cancelled
    await handle_cancel_reason(
        callback=callback,
        callback_data=CancelReasonCallback(action="pick", lead_id=new_lead.id, index=0),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    callback.answer.assert_awaited()
    # Lead cancelled.
    lead = await LeadRepository(session).get(new_lead.id)
    assert lead.status == LeadStatus.CANCELLED

    # MY_LEAD_DETAIL re-rendered.
    callback.bot.edit_message_text.assert_awaited_once()
    text = callback.bot.edit_message_text.await_args.kwargs["text"]
    assert new_lead.public_id in text


# ─── Test 3: pick custom reason transitions FSM ────────────────────────────


@pytest.mark.asyncio
async def test_pick_custom_reason_transitions_to_writing(
    content, state, session: AsyncSession, current_user, new_lead
):
    """Picking 'Своя причина' sets FSM to writing_custom_reason."""
    from app.bot.screens.cancel_reason import MY_LEAD_CANCEL_REASON_SCREEN_ID
    from app.bot.ui.navigation import push

    await push(state, MY_LEAD_CANCEL_REASON_SCREEN_ID)

    callback = _callback()

    # "Своя причина" is the last entry (index 3) in default texts.yaml
    reasons = content.texts.close_reasons.cancelled
    custom_index = next((i for i, r in enumerate(reasons) if r == "Своя причина"), len(reasons) - 1)

    await handle_cancel_reason(
        callback=callback,
        callback_data=CancelReasonCallback(
            action="custom", lead_id=new_lead.id, index=custom_index
        ),
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    callback.answer.assert_awaited()
    assert await state.get_state() == MyLeadCancelState.writing_custom_reason.state
    data = await state.get_data()
    assert data["cancel_target_lead_id"] == new_lead.id

    # Lead still NEW at this point.
    lead = await LeadRepository(session).get(new_lead.id)
    assert lead.status == LeadStatus.NEW


# ─── Test 4: custom reason text message completes cancellation ─────────────


@pytest.mark.asyncio
async def test_custom_reason_text_cancels_lead(
    content, state, session: AsyncSession, current_user, new_lead
):
    """Sending a custom reason text cancels the lead and re-renders MY_LEAD_DETAIL."""
    from app.bot.screens.cancel_reason import MY_LEAD_CANCEL_REASON_SCREEN_ID
    from app.bot.ui.navigation import push

    await push(state, MY_LEAD_CANCEL_REASON_SCREEN_ID)
    await state.set_state(MyLeadCancelState.writing_custom_reason)
    await state.update_data({"cancel_target_lead_id": new_lead.id})

    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1001))
    msg = MagicMock()
    msg.text = "Нашёл другого исполнителя"
    msg.bot = bot
    msg.chat = MagicMock(id=42)
    msg.answer = AsyncMock()

    await handle_cancel_custom_reason(
        message=msg,
        state=state,
        session=session,
        current_user=current_user,
        content=content,
    )

    msg.answer.assert_awaited()
    assert await state.get_state() is None
    lead = await LeadRepository(session).get(new_lead.id)
    assert lead.status == LeadStatus.CANCELLED
