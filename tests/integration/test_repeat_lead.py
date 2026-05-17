"""Integration tests for LeadService.build_draft_from_lead and the repeat flow."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.routers.user.my_leads import handle_lead_detail_action
from app.bot.screens.my_leads import MyLeadDetailCallback
from app.bot.states.lead import LeadFormState
from app.bot.ui.navigation import get_stack
from app.core.config import Settings
from app.core.exceptions import PermissionDeniedError
from app.db.repositories.forms import FormRepository
from app.db.repositories.users import UserRepository
from app.schemas.lead import LeadAnswerInput, LeadCreateInput
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from app.services.leads import LeadService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"
_BUNDLE = ContentService.load(_CONTENT_DIR)


@pytest.fixture
def content():
    return ContentService(_BUNDLE)


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


@pytest.fixture
async def user(session: AsyncSession):
    await ensure_seed_data(session, _BUNDLE)
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
async def other_user(session: AsyncSession):
    repo = UserRepository(session)
    return await repo.upsert_telegram_user(
        telegram_id=99,
        username="other_user",
        first_name="Other",
        last_name=None,
        is_admin=False,
    )


@pytest.fixture
async def lead_with_answers(session: AsyncSession, user):
    category = await FormRepository(session).get_category_by_slug("telegram_bot")
    form = await FormRepository(session).get_active_form(category.id)
    service = LeadService(session, Settings(admin_ids=[999]))
    return await service.create_lead(
        LeadCreateInput(
            user_id=user.id,
            category_id=category.id,
            title=category.title,
            description="Need a telegram bot",
            contact_name="Test",
            contact_phone="+79991234567",
            contact_username="test_user",
            answers=[
                LeadAnswerInput(
                    question_id=form.questions[0].id,
                    key=form.questions[0].key,
                    value_text="Need a lead bot",
                )
            ],
        )
    )


# ─── Unit-level tests for build_draft_from_lead ────────────────────────────


@pytest.mark.asyncio
async def test_build_draft_copies_answers(session: AsyncSession, user, lead_with_answers):
    """build_draft_from_lead returns dict with all answers copied and new submission_key."""
    service = LeadService(session, Settings(admin_ids=[999]))
    draft = await service.build_draft_from_lead(lead_id=lead_with_answers.id, actor=user)

    assert draft["category_id"] == lead_with_answers.category_id
    assert draft["source"] == "repeat"
    assert draft["submission_key"] != lead_with_answers.submission_key
    assert len(draft["submission_key"]) == 32  # uuid4().hex
    assert len(draft["answers"]) == 1
    assert draft["answers"][0]["key"] == "goal"
    assert draft["answers"][0]["value_text"] == "Need a lead bot"
    assert draft["files"] == []
    assert draft["contact_phone"] == "+79991234567"


@pytest.mark.asyncio
async def test_build_draft_raises_for_other_users_lead(
    session: AsyncSession, user, other_user, lead_with_answers
):
    """build_draft_from_lead raises PermissionDeniedError when actor is not the lead owner."""
    service = LeadService(session, Settings(admin_ids=[999]))
    with pytest.raises(PermissionDeniedError):
        await service.build_draft_from_lead(lead_id=lead_with_answers.id, actor=other_user)


@pytest.mark.asyncio
async def test_build_draft_raises_for_nonexistent_lead(session: AsyncSession, user):
    """build_draft_from_lead raises NotFoundError for a missing lead."""
    from app.core.exceptions import NotFoundError

    service = LeadService(session, Settings(admin_ids=[999]))
    with pytest.raises(NotFoundError):
        await service.build_draft_from_lead(lead_id=999999, actor=user)


# ─── Integration test for the repeat callback handler ──────────────────────


def _callback(message_id=999):
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=message_id))
    callback = MagicMock()
    callback.bot = bot
    callback.message = MagicMock(chat=MagicMock(id=42), message_id=message_id)
    callback.answer = AsyncMock()
    return callback


@pytest.mark.asyncio
async def test_repeat_callback_sets_confirming_state(
    content, state, session: AsyncSession, user, lead_with_answers
):
    """Clicking repeat pushes lead_confirm to nav_stack and sets LeadFormState.confirming."""
    await state.update_data(
        {
            "root_message_id": 999,
            "nav_stack": ["main_menu", "my_leads", "my_lead_detail"],
        }
    )
    callback = _callback()

    await handle_lead_detail_action(
        callback=callback,
        callback_data=MyLeadDetailCallback(action="repeat", lead_id=lead_with_answers.id),
        state=state,
        content=content,
        session=session,
        current_user=user,
    )

    assert await state.get_state() == LeadFormState.confirming.state
    stack = await get_stack(state)
    assert stack[-1] == "lead_confirm"
    data = await state.get_data()
    assert data["source"] == "repeat"
    assert len(data["answers"]) == 1
    callback.answer.assert_awaited()


@pytest.mark.asyncio
async def test_repeat_callback_rejects_other_users_lead(
    content, state, session: AsyncSession, other_user, lead_with_answers
):
    """Repeat handler shows alert when actor doesn't own the lead."""
    await state.update_data(
        {
            "root_message_id": 999,
            "nav_stack": ["main_menu", "my_leads", "my_lead_detail"],
        }
    )
    callback = _callback()

    await handle_lead_detail_action(
        callback=callback,
        callback_data=MyLeadDetailCallback(action="repeat", lead_id=lead_with_answers.id),
        state=state,
        content=content,
        session=session,
        current_user=other_user,
    )

    # Should have shown an alert but NOT changed state.
    callback.answer.assert_awaited()
    assert await state.get_state() is None
