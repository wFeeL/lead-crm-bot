"""Integration tests: support handler creates a real lead with source='support'."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.routers.user.support import handle_support_message
from app.bot.states.support import SupportState
from app.db.repositories.forms import FormRepository
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.services.content import ContentService
from app.services.forms import ensure_seed_data

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
    await fsm.set_state(SupportState.writing_message)
    await fsm.update_data(
        {"root_message_id": 999, "nav_stack": ["main_menu", "support", "support_writing"]}
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


def _message(text: str) -> tuple:
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1000))
    msg = MagicMock()
    msg.text = text
    msg.bot = bot
    msg.chat = MagicMock(id=42)
    msg.answer = AsyncMock()
    return msg, bot


@pytest.mark.asyncio
async def test_support_message_creates_lead_with_support_source(
    content, state, session: AsyncSession, current_user
):
    """A support message creates a lead with category.slug='support' and source='support'."""
    msg, bot = _message("помогите!")

    await handle_support_message(
        message=msg,
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    # State cleared.
    assert await state.get_state() is None

    # Lead created with correct category and source.
    repo = LeadRepository(session)
    leads = await repo.list_by_user(current_user.id)
    assert len(leads) == 1
    lead = leads[0]
    assert lead.source == "support"
    assert lead.category is not None
    assert lead.category.slug == "support"
    assert lead.description == "помогите!"

    # Answer stored.
    assert len(lead.answers) == 1
    assert lead.answers[0].value_text == "помогите!"

    # User notified with lead public_id.
    msg.answer.assert_awaited()
    args, _ = msg.answer.await_args
    assert lead.public_id in args[0]


@pytest.mark.asyncio
async def test_support_empty_text_does_not_create_lead(
    content, state, session: AsyncSession, current_user
):
    """Empty/whitespace message does NOT create a lead and keeps FSM state."""
    msg, _ = _message("   ")

    await handle_support_message(
        message=msg,
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    # State still in writing mode.
    assert await state.get_state() == SupportState.writing_message.state

    # No leads created.
    repo = LeadRepository(session)
    leads = await repo.list_by_user(current_user.id)
    assert len(leads) == 0

    msg.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_support_message_clears_state_and_returns_to_main_menu(
    content, state, session: AsyncSession, current_user
):
    """After successful support message, state is cleared and main menu is rendered."""
    msg, bot = _message("У меня вопрос по заявке.")

    await handle_support_message(
        message=msg,
        state=state,
        content=content,
        session=session,
        current_user=current_user,
    )

    assert await state.get_state() is None
    # Main menu rendered via bot.edit_message_text or bot.send_message.
    assert (bot.edit_message_text.await_count + bot.send_message.await_count) >= 1
