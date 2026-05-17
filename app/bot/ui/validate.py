from functools import wraps
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery


def validate_question_context(handler):
    """Ensure the callback's question_id matches the current question in FSM.

    Used on LeadQuestion{Skip,Choice,Back}Callback handlers — they each had
    duplicated context checks (see commit history of lead_create.py before
    Step 3).
    """

    @wraps(handler)
    async def wrapper(
        callback: CallbackQuery,
        callback_data,
        state: FSMContext,
        **kwargs: Any,
    ) -> Any:
        data = await state.get_data()
        questions = data.get("questions") or []
        index = data.get("question_index", 0)
        if not questions or index >= len(questions):
            await callback.answer("Этот шаг уже неактуален.", show_alert=True)
            return
        current_question = questions[index]
        if current_question.get("id") != getattr(callback_data, "question_id", None):
            await callback.answer("Этот шаг уже неактуален.", show_alert=True)
            return
        return await handler(
            callback=callback,
            callback_data=callback_data,
            state=state,
            current_question=current_question,
            **kwargs,
        )

    return wrapper
