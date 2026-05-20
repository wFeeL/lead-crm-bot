"""Contact step is a single-message screen — text + reply-keyboard."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from app.bot.screens.lead_contact import (
    LEAD_CONTACT_PROMPT_SCREEN_ID,
    make_contact_reply_keyboard,
    send_contact_prompt,
)


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


def test_screen_id_is_stable():
    assert LEAD_CONTACT_PROMPT_SCREEN_ID == "lead_contact_prompt"


def test_make_contact_reply_keyboard_has_request_contact_button():
    kb = make_contact_reply_keyboard()
    btn = kb.keyboard[0][0]
    assert btn.request_contact is True
    # Single button — no clutter.
    assert len(kb.keyboard) == 1
    assert len(kb.keyboard[0]) == 1


async def test_send_contact_prompt_sends_one_message_with_reply_keyboard(state):
    """The whole point of the redesign: ONE message, not two."""
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=777))
    bot.delete_message = AsyncMock()

    await send_contact_prompt(bot=bot, chat_id=42, state=state)

    bot.send_message.assert_awaited_once()
    call_kwargs = bot.send_message.await_args.kwargs
    assert "Контакт" in call_kwargs["text"]
    # reply_markup must carry the request_contact button.
    rk = call_kwargs["reply_markup"]
    assert rk.keyboard[0][0].request_contact is True

    # Root pointer updated so subsequent screens know which message to replace.
    data = await state.get_data()
    assert data["root_message_id"] == 777


async def test_send_contact_prompt_deletes_old_root_first(state):
    """If a previous screen exists, delete it before sending the contact prompt
    so the chat doesn't end up with two visible screens."""
    await state.update_data(root_message_id=555)
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    bot.delete_message = AsyncMock()

    await send_contact_prompt(bot=bot, chat_id=42, state=state)

    bot.delete_message.assert_awaited_once_with(chat_id=42, message_id=555)
