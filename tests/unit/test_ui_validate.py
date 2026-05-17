from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from app.bot.ui.validate import validate_question_context


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


async def test_decorator_passes_current_question_kwarg_on_match(state: FSMContext):
    await state.update_data(questions=[{"id": 5, "key": "a"}], question_index=0)

    @validate_question_context
    async def handler(callback, callback_data, state, current_question):
        return current_question

    callback = AsyncMock()
    callback_data = SimpleNamespace(question_id=5)
    result = await handler(callback=callback, callback_data=callback_data, state=state)
    assert result == {"id": 5, "key": "a"}


async def test_decorator_alerts_on_id_mismatch(state: FSMContext):
    await state.update_data(questions=[{"id": 5}], question_index=0)

    @validate_question_context
    async def handler(callback, callback_data, state, current_question):
        raise AssertionError("should not be called")

    callback = AsyncMock()
    callback_data = SimpleNamespace(question_id=999)
    await handler(callback=callback, callback_data=callback_data, state=state)
    callback.answer.assert_awaited_once()


async def test_decorator_alerts_on_empty_questions(state: FSMContext):
    @validate_question_context
    async def handler(callback, callback_data, state, current_question):
        raise AssertionError("should not be called")

    callback = AsyncMock()
    callback_data = SimpleNamespace(question_id=1)
    await handler(callback=callback, callback_data=callback_data, state=state)
    callback.answer.assert_awaited_once()


async def test_decorator_alerts_on_index_out_of_range(state: FSMContext):
    await state.update_data(questions=[{"id": 1}], question_index=99)

    @validate_question_context
    async def handler(callback, callback_data, state, current_question):
        raise AssertionError("should not be called")

    callback = AsyncMock()
    callback_data = SimpleNamespace(question_id=1)
    await handler(callback=callback, callback_data=callback_data, state=state)
    callback.answer.assert_awaited_once()
