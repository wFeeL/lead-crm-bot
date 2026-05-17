"""Integration tests for the lead-create FSM flow."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.routers.user.lead_create import (
    on_confirm_action,
    on_contact,
    on_files_action,
    on_pick_category,
    on_text_answer,
    start_lead_create,
)
from app.bot.screens.lead_category import LeadCategoryCallback
from app.bot.screens.lead_confirm import LeadConfirmCallback
from app.bot.screens.lead_files import LeadFilesCallback
from app.bot.states.lead import LeadFormState
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.services.content import ContentService
from app.services.forms import ensure_seed_data
from sqlalchemy.ext.asyncio import AsyncSession

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


@pytest.fixture
def content():
    return ContentService(ContentService.load(_CONTENT_DIR))


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    ctx = FSMContext(storage=storage, key=key)
    # Pre-set root_message_id so render_screen edits instead of sending.
    await ctx.update_data({"root_message_id": 999, "nav_stack": ["main_menu"]})
    return ctx


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


def _bot():
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    bot.edit_message_text = AsyncMock()
    return bot


def _callback(bot, message_id=999):
    cb = MagicMock()
    cb.bot = bot
    cb.message = MagicMock(chat=MagicMock(id=42), message_id=message_id)
    cb.answer = AsyncMock()
    return cb


def _message(bot, text):
    msg = MagicMock()
    msg.bot = bot
    msg.chat = MagicMock(id=42)
    msg.text = text
    msg.contact = None
    msg.answer = AsyncMock(return_value=MagicMock(delete=AsyncMock()))
    return msg


# ---------------------------------------------------------------------------
# Test 1: start pushes category screen
# ---------------------------------------------------------------------------


async def test_start_lead_create_pushes_category_screen(content, state, session, current_user):
    """start_lead_create sets choosing_category and pushes lead_category onto the nav stack."""
    bot = _bot()
    await start_lead_create(bot=bot, chat_id=42, state=state, session=session, content=content)

    assert await state.get_state() == LeadFormState.choosing_category.state
    data = await state.get_data()
    assert "lead_category" in data["nav_stack"]
    assert "submission_key" in data
    bot.edit_message_text.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 2: pick category loads questions
# ---------------------------------------------------------------------------


async def test_pick_category_loads_questions(content, state, session, current_user):
    """Picking telegram_bot transitions to answering_questions with questions loaded."""
    await start_lead_create(bot=_bot(), chat_id=42, state=state, session=session, content=content)

    bot = _bot()
    callback = _callback(bot)
    await on_pick_category(
        callback=callback,
        callback_data=LeadCategoryCallback(slug="telegram_bot"),
        state=state,
        session=session,
        content=content,
    )

    assert await state.get_state() == LeadFormState.answering_questions.state
    data = await state.get_data()
    assert data["category_slug"] == "telegram_bot"
    assert len(data["questions"]) > 0
    assert data["question_index"] == 0
    assert data["answers"] == []


# ---------------------------------------------------------------------------
# Test 3: text answer advances question index
# ---------------------------------------------------------------------------


async def test_text_answer_advances_to_next_question(content, state, session, current_user):
    """Submitting a text answer saves it and increments question_index."""
    await start_lead_create(bot=_bot(), chat_id=42, state=state, session=session, content=content)
    await on_pick_category(
        callback=_callback(_bot()),
        callback_data=LeadCategoryCallback(slug="telegram_bot"),
        state=state,
        session=session,
        content=content,
    )

    bot = _bot()
    message = _message(bot, "Сделать бота для заявок")
    await on_text_answer(message=message, state=state, content=content)

    data = await state.get_data()
    assert data["question_index"] == 1
    assert len(data["answers"]) == 1
    assert data["answers"][0]["value_text"] == "Сделать бота для заявок"


# ---------------------------------------------------------------------------
# Test 4: full happy path creates lead in DB
# ---------------------------------------------------------------------------


async def test_full_happy_path_creates_lead(content, state, session, current_user):
    """End-to-end: pick category, answer all questions, skip files, give contact, submit."""
    # Patch NotificationService so admin notifications don't fail in test environment.
    with patch("app.bot.routers.user.lead_create.NotificationService") as mock_notifier_cls:
        mock_notifier = MagicMock()
        mock_notifier.notify_new_lead = AsyncMock()
        mock_notifier_cls.return_value = mock_notifier

        await start_lead_create(
            bot=_bot(), chat_id=42, state=state, session=session, content=content
        )
        await on_pick_category(
            callback=_callback(_bot()),
            callback_data=LeadCategoryCallback(slug="telegram_bot"),
            state=state,
            session=session,
            content=content,
        )

        # Answer all questions (telegram_bot has 3: goal/long_text, deadline/text, budget/text).
        data = await state.get_data()
        n_questions = len(data["questions"])
        answers_text = ["Бот для приёма заявок", "Через месяц", "100 тысяч рублей"]
        for i in range(n_questions):
            msg = _message(_bot(), answers_text[i] if i < len(answers_text) else f"Ответ {i + 1}")
            await on_text_answer(message=msg, state=state, content=content)

        # After all answers → uploading_files.
        assert await state.get_state() == LeadFormState.uploading_files.state

        # Continue without uploading.
        callback = _callback(_bot())
        await on_files_action(
            callback=callback,
            callback_data=LeadFilesCallback(action="continue"),
            state=state,
            content=content,
        )
        assert await state.get_state() == LeadFormState.entering_contact.state

        # Give contact as text.
        msg = _message(_bot(), "+7 999 111 2233")
        await on_contact(message=msg, state=state, content=content)
        assert await state.get_state() == LeadFormState.confirming.state

        # Submit.
        callback = _callback(_bot())
        await on_confirm_action(
            callback=callback,
            callback_data=LeadConfirmCallback(action="submit"),
            state=state,
            session=session,
            current_user=current_user,
            content=content,
        )

    # Verify state cleared after submit.
    assert await state.get_state() is None

    # Verify lead was created in DB.
    repo = LeadRepository(session)
    leads = await repo.list_by_user(current_user.id, limit=10, offset=0)
    assert len(leads) == 1
    lead = leads[0]
    assert lead.category.slug == "telegram_bot"
    assert "+7 999 111 2233" in (lead.contact_phone or "")


# ---------------------------------------------------------------------------
# Test 5: cancel mid-flow clears state
# ---------------------------------------------------------------------------


async def test_cancel_mid_flow_clears_state(content, state, session, current_user):
    """Simulates escape: after starting the flow, clearing state leaves FSM state as None."""
    await start_lead_create(bot=_bot(), chat_id=42, state=state, session=session, content=content)
    await on_pick_category(
        callback=_callback(_bot()),
        callback_data=LeadCategoryCallback(slug="telegram_bot"),
        state=state,
        session=session,
        content=content,
    )
    # Confirm we are mid-flow.
    assert await state.get_state() == LeadFormState.answering_questions.state

    # EscapeMiddleware is tested separately; here we just verify state.clear() works.
    await state.clear()
    assert await state.get_state() is None
    data = await state.get_data()
    # After clear(), data is empty.
    assert data == {}


# ---------------------------------------------------------------------------
# Test 6: edit_answers from confirm pops last answer
# ---------------------------------------------------------------------------


async def test_edit_answers_from_confirm_pops_last_answer(content, state, session, current_user):
    """From confirming, edit_answers goes back to answering_questions with last answer popped."""
    questions = [
        {
            "id": 1,
            "key": "goal",
            "text": "Q1",
            "type": "long_text",
            "required": True,
            "options": [],
        },
        {
            "id": 2,
            "key": "deadline",
            "text": "Q2",
            "type": "text",
            "required": False,
            "options": [],
        },
        {"id": 3, "key": "budget", "text": "Q3", "type": "text", "required": False, "options": []},
    ]
    answers = [
        {"question_id": 1, "key": "goal", "question_text": "Q1", "value_text": "A1"},
        {"question_id": 2, "key": "deadline", "question_text": "Q2", "value_text": "A2"},
        {"question_id": 3, "key": "budget", "question_text": "Q3", "value_text": "A3"},
    ]
    await state.set_state(LeadFormState.confirming)
    await state.update_data(
        {
            "root_message_id": 999,
            "nav_stack": [
                "main_menu",
                "lead_category",
                "lead_question",
                "lead_upload_files",
                "lead_contact_prompt",
                "lead_confirm",
            ],
            "category_id": 1,
            "category_title": "Test",
            "category_slug": "telegram_bot",
            "questions": questions,
            "question_index": 3,
            "answers": answers,
            "files": [],
            "contact": "+7",
            "submission_key": "xxx",
        }
    )

    bot = _bot()
    callback = _callback(bot)
    await on_confirm_action(
        callback=callback,
        callback_data=LeadConfirmCallback(action="edit_answers"),
        state=state,
        session=session,
        current_user=current_user,
        content=content,
    )

    assert await state.get_state() == LeadFormState.answering_questions.state
    data = await state.get_data()
    assert len(data["answers"]) == 2
    assert data["question_index"] == 2
