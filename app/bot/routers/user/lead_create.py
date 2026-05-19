from typing import Any
from uuid import uuid4

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.screens.lead_category import (
    LEAD_CATEGORY_SCREEN_ID,
    LeadCategoryCallback,
    render_lead_category,
)
from app.bot.screens.lead_confirm import (
    LEAD_CONFIRM_SCREEN_ID,
    LeadConfirmCallback,
    render_lead_confirm,
)
from app.bot.screens.lead_contact import (
    LEAD_CONTACT_PROMPT_SCREEN_ID,
    make_contact_reply_keyboard,
    render_lead_contact_prompt,
)
from app.bot.screens.lead_done import render_lead_done
from app.bot.screens.lead_edit_answers import (
    LEAD_EDIT_ANSWERS_SCREEN_ID,
    LeadEditAnswerCallback,
    render_lead_edit_answers,
)
from app.bot.screens.lead_files import (
    LEAD_UPLOAD_FILES_SCREEN_ID,
    LeadFilesCallback,
    render_lead_upload_files,
)
from app.bot.screens.lead_question import (
    LEAD_QUESTION_SCREEN_ID,
    LeadQuestionBackCallback,
    LeadQuestionChoiceCallback,
    LeadQuestionSkipCallback,
    render_lead_question,
)
from app.bot.states.lead import LeadFormState
from app.bot.ui.navigation import MAIN_MENU_SCREEN_ID, get_stack, pop, push
from app.bot.ui.render import render_screen
from app.bot.ui.validate import validate_question_context
from app.core.config import get_settings
from app.core.constants import FileType, QuestionType
from app.core.exceptions import AppError, ValidationError
from app.db.models.user import User
from app.db.repositories.forms import FormRepository
from app.schemas.lead import LeadAnswerInput, LeadCreateInput, LeadFileInput
from app.services.content import ContentService
from app.services.leads import LeadService
from app.services.notifications import NotificationService
from app.services.validators import (
    validate_date,
    validate_email,
    validate_number,
    validate_phone,
    validate_time,
)

router = Router(name="lead_create")


# ============= Helper functions (preserved from old code) =============


def _normalize_options(raw_options: Any) -> list[str]:
    if raw_options is None:
        return []
    if isinstance(raw_options, dict):
        raw_options = raw_options.get("options") or raw_options.get("values") or []
    if not isinstance(raw_options, list):
        return []
    options: list[str] = []
    for item in raw_options:
        if isinstance(item, dict):
            value = item.get("label") or item.get("title") or item.get("value")
        else:
            value = item
        if value is not None:
            options.append(str(value))
    return options


def _serialize_question(question) -> dict[str, Any]:
    return {
        "id": question.id,
        "key": question.key,
        "text": question.question_text,
        "type": question.question_type,
        "required": question.is_required,
        "options": _normalize_options(question.options_json),
    }


def _normalize_answer_value(question: dict[str, Any], raw_text: str) -> str:
    text = raw_text.strip()
    question_type = QuestionType(question["type"])
    if question_type == QuestionType.PHONE:
        return validate_phone(text)
    if question_type == QuestionType.EMAIL:
        return validate_email(text)
    if question_type == QuestionType.NUMBER:
        return validate_number(text)
    if question_type == QuestionType.DATE:
        return validate_date(text)
    if question_type == QuestionType.TIME:
        return validate_time(text)
    if (
        question_type == QuestionType.CHOICE
        and question["options"]
        and text not in question["options"]
    ):
        raise ValidationError("choose one of the options")
    return text


def _validation_hint(question: dict[str, Any]) -> str:
    hints = {
        QuestionType.PHONE: "Введите телефон в формате +79990000000.",
        QuestionType.EMAIL: "Введите корректный email.",
        QuestionType.NUMBER: "Введите число.",
        QuestionType.DATE: "Введите дату в формате ДД.ММ.ГГГГ.",
        QuestionType.TIME: "Введите время в формате ЧЧ:ММ.",
        QuestionType.CHOICE: "Выберите один из вариантов кнопкой.",
    }
    return hints.get(QuestionType(question["type"]), "Проверьте ответ и попробуйте еще раз.")


def _file_from_message(message: Message) -> dict[str, Any] | None:
    if message.photo:
        photo = message.photo[-1]
        return {
            "telegram_file_id": photo.file_id,
            "file_unique_id": photo.file_unique_id,
            "file_type": FileType.PHOTO,
            "file_name": None,
            "mime_type": None,
            "size": photo.file_size,
        }
    if message.document:
        document = message.document
        return {
            "telegram_file_id": document.file_id,
            "file_unique_id": document.file_unique_id,
            "file_type": FileType.DOCUMENT,
            "file_name": document.file_name,
            "mime_type": document.mime_type,
            "size": document.file_size,
        }
    return None


# ============= Entry: launched from menu router =============


async def start_lead_create(
    *,
    bot,
    chat_id: int,
    state: FSMContext,
    session: AsyncSession,
    content: ContentService,
) -> None:
    """Entry point called by menu router's create_lead branch."""
    repo = FormRepository(session)
    categories = await repo.list_categories()
    await state.set_state(LeadFormState.choosing_category)
    await state.update_data(
        submission_key=uuid4().hex,
        questions=[],
        question_index=0,
        answers=[],
        files=[],
    )
    await push(state, LEAD_CATEGORY_SCREEN_ID)
    stack = await get_stack(state)
    screen = render_lead_category(content=content, categories=categories, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


# ============= Step 1: pick category =============


@router.callback_query(StateFilter(LeadFormState.choosing_category), LeadCategoryCallback.filter())
async def on_pick_category(
    callback: CallbackQuery,
    callback_data: LeadCategoryCallback,
    state: FSMContext,
    session: AsyncSession,
    content: ContentService,
) -> None:
    repo = FormRepository(session)
    category = await repo.get_category_by_slug(callback_data.slug)
    if category is None or getattr(category, "is_internal", False):
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    form = await repo.get_active_form(category.id)
    if form is None or not form.questions:
        await callback.answer("Форма не настроена.", show_alert=True)
        return

    questions = [_serialize_question(q) for q in form.questions]
    await state.update_data(
        category_id=category.id,
        category_title=category.title,
        category_slug=category.slug,
        questions=questions,
        question_index=0,
        answers=[],
        files=[],
    )
    await state.set_state(LeadFormState.answering_questions)
    await _render_current_question(callback.bot, callback.message.chat.id, state, content)
    await callback.answer()


async def _render_current_question(bot, chat_id, state, content) -> None:
    data = await state.get_data()
    questions = data["questions"]
    index = data["question_index"]
    question = questions[index]
    await push(state, LEAD_QUESTION_SCREEN_ID)
    stack = await get_stack(state)
    screen = render_lead_question(
        content=content,
        question=question,
        index=index,
        total=len(questions),
        stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


# ============= Step 2: collect answers (text + choice + skip + back) =============


@router.message(StateFilter(LeadFormState.answering_questions), F.text)
async def on_text_answer(
    message: Message,
    state: FSMContext,
    content: ContentService,
) -> None:
    """Accept a text answer for the current question."""
    data = await state.get_data()
    questions = data["questions"]
    index = data["question_index"]
    question = questions[index]
    raw = (message.text or "").strip()
    if question["required"] and not raw:
        await message.answer("Ответ обязателен. Напишите текстом.")
        return
    try:
        value_text = _normalize_answer_value(question, raw) if raw else ""
    except ValidationError:
        await message.answer(_validation_hint(question))
        return
    await _save_and_advance(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        content=content,
        value_text=value_text,
    )


@router.callback_query(
    StateFilter(LeadFormState.answering_questions),
    LeadQuestionSkipCallback.filter(),
)
@validate_question_context
async def on_skip_question(
    callback: CallbackQuery,
    callback_data: LeadQuestionSkipCallback,
    state: FSMContext,
    content: ContentService,
    current_question: dict,
) -> None:
    if current_question["required"]:
        await callback.answer("Этот вопрос обязателен.", show_alert=True)
        return
    await _save_and_advance(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        content=content,
        value_text="",
    )
    await callback.answer()


@router.callback_query(
    StateFilter(LeadFormState.answering_questions),
    LeadQuestionChoiceCallback.filter(),
)
@validate_question_context
async def on_choice_answer(
    callback: CallbackQuery,
    callback_data: LeadQuestionChoiceCallback,
    state: FSMContext,
    content: ContentService,
    current_question: dict,
) -> None:
    try:
        value_text = current_question["options"][callback_data.option_index]
    except IndexError:
        await callback.answer("Вариант не найден.", show_alert=True)
        return
    await _save_and_advance(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        content=content,
        value_text=value_text,
    )
    await callback.answer()


@router.callback_query(
    StateFilter(LeadFormState.answering_questions),
    LeadQuestionBackCallback.filter(),
)
@validate_question_context
async def on_back_question(
    callback: CallbackQuery,
    callback_data: LeadQuestionBackCallback,
    state: FSMContext,
    content: ContentService,
    current_question: dict,
) -> None:
    data = await state.get_data()
    index = data["question_index"]
    answers = data.get("answers", [])
    if index <= 0:
        await callback.answer("Это первый вопрос.", show_alert=True)
        return
    index -= 1
    if answers:
        answers.pop()
    await state.update_data(answers=answers, question_index=index)
    await _render_current_question(callback.bot, callback.message.chat.id, state, content)
    await callback.answer()


async def _save_and_advance(
    *,
    bot,
    chat_id: int,
    state: FSMContext,
    content: ContentService,
    value_text: str,
) -> None:
    data = await state.get_data()
    questions = data["questions"]
    index = data["question_index"]
    question = questions[index]
    answers = data.get("answers", [])
    answers.append(
        {
            "question_id": question["id"],
            "key": question["key"],
            "question_text": question["text"],
            "value_text": value_text,
        }
    )
    index += 1
    await state.update_data(answers=answers, question_index=index)
    if index >= len(questions):
        await state.set_state(LeadFormState.uploading_files)
        await push(state, LEAD_UPLOAD_FILES_SCREEN_ID)
        stack = await get_stack(state)
        files = (await state.get_data()).get("files", [])
        screen = render_lead_upload_files(
            content=content,
            files=files,
            max_files=get_settings().max_files_per_lead,
            stack=stack,
        )
        await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)
    else:
        await _render_current_question(bot, chat_id, state, content)


# ============= Step 3: file upload =============


@router.message(StateFilter(LeadFormState.uploading_files), F.photo | F.document)
async def on_file_received(
    message: Message,
    state: FSMContext,
    content: ContentService,
) -> None:
    file_data = _file_from_message(message)
    if file_data is None:
        return
    settings = get_settings()
    data = await state.get_data()
    files = data.get("files", [])
    if len(files) >= settings.max_files_per_lead:
        await message.answer("Достигнут лимит файлов.")
        return
    if file_data.get("size") and file_data["size"] > settings.max_file_size_bytes:
        await message.answer("Файл слишком большой.")
        return
    files.append(file_data)
    await state.update_data(files=files)
    stack = await get_stack(state)
    screen = render_lead_upload_files(
        content=content,
        files=files,
        max_files=settings.max_files_per_lead,
        stack=stack,
    )
    await render_screen(bot=message.bot, chat_id=message.chat.id, state=state, screen=screen)


@router.callback_query(
    StateFilter(LeadFormState.uploading_files),
    LeadFilesCallback.filter(),
)
async def on_files_action(
    callback: CallbackQuery,
    callback_data: LeadFilesCallback,
    state: FSMContext,
    content: ContentService,
) -> None:
    data = await state.get_data()
    settings = get_settings()
    if callback_data.action == "delete_last":
        files = data.get("files", [])
        if files:
            files.pop()
            await state.update_data(files=files)
            stack = await get_stack(state)
            screen = render_lead_upload_files(
                content=content,
                files=files,
                max_files=settings.max_files_per_lead,
                stack=stack,
            )
            await render_screen(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                state=state,
                screen=screen,
            )
    elif callback_data.action == "back_to_questions":
        # Go back to last answered question.
        answers = data.get("answers", [])
        if answers:
            answers.pop()
            await state.update_data(answers=answers, question_index=len(answers))
        await state.set_state(LeadFormState.answering_questions)
        # Pop the upload-files screen from stack.
        await pop(state)
        await _render_current_question(
            callback.bot,
            callback.message.chat.id,
            state,
            content,
        )
    elif callback_data.action == "continue":
        # Move to contact prompt.
        await state.set_state(LeadFormState.entering_contact)
        await push(state, LEAD_CONTACT_PROMPT_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_lead_contact_prompt(content=content, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        # Send the contact reply-keyboard as a separate prompt.
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text="📞 Нажмите кнопку, чтобы поделиться телефоном, или напишите контакт текстом.",
            reply_markup=make_contact_reply_keyboard(),
        )
    await callback.answer()


# ============= Step 4: collect contact =============


@router.message(StateFilter(LeadFormState.entering_contact))
async def on_contact(
    message: Message,
    state: FSMContext,
    content: ContentService,
) -> None:
    """Accept contact: phone (via button), username (text starting with @), or free text."""
    contact = ""
    updates: dict[str, str] = {}
    if message.contact and message.contact.phone_number:
        contact = message.contact.phone_number.strip()
        updates["contact_phone"] = contact
    else:
        contact = (message.text or "").strip()
        if contact.startswith("@"):
            updates["contact_username"] = contact.removeprefix("@")
        else:
            updates["contact_phone"] = contact
    if not contact:
        await message.answer(
            "Контакт обязателен. Напишите телефон, @username или другой способ связи."
        )
        return
    updates["contact"] = contact
    await state.update_data(**updates)
    # Remove the reply-keyboard with a transient message.
    transient = await message.answer("✅ Контакт сохранён.", reply_markup=ReplyKeyboardRemove())
    # Best-effort delete to keep chat clean.
    try:
        await transient.delete()
    except Exception:
        pass
    await state.set_state(LeadFormState.confirming)
    await push(state, LEAD_CONFIRM_SCREEN_ID)
    stack = await get_stack(state)
    data = await state.get_data()
    screen = render_lead_confirm(content=content, draft=data, stack=stack)
    # End-of-wizard summary must be a fresh message so the user can scroll back
    # over their answers; editing the old wizard message hides everything.
    await render_screen(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        screen=screen,
        force_new=True,
    )


# ============= Step 5: confirm & submit =============


@router.callback_query(StateFilter(LeadFormState.confirming), LeadConfirmCallback.filter())
async def on_confirm_action(
    callback: CallbackQuery,
    callback_data: LeadConfirmCallback,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    content: ContentService,
) -> None:
    if callback_data.action == "submit":
        await _submit_lead(callback, state, session, current_user, content)
    elif callback_data.action == "edit_answers":
        # Open the edit-answers list: user picks WHICH answer to change, the
        # rest are preserved.
        await push(state, LEAD_EDIT_ANSWERS_SCREEN_ID)
        data = await state.get_data()
        stack = await get_stack(state)
        screen = render_lead_edit_answers(content=content, draft=data, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer()
    elif callback_data.action == "add_file":
        await state.set_state(LeadFormState.uploading_files)
        await pop(state)  # leave confirm
        data = await state.get_data()
        settings = get_settings()
        stack = await get_stack(state)
        screen = render_lead_upload_files(
            content=content,
            files=data.get("files", []),
            max_files=settings.max_files_per_lead,
            stack=stack,
        )
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer()


async def _submit_lead(callback, state, session, current_user, content):
    await callback.answer("Отправляем заявку...")
    data = await state.get_data()
    answers = [
        LeadAnswerInput(
            question_id=item["question_id"],
            key=item["key"],
            value_text=item.get("value_text"),
        )
        for item in data.get("answers", [])
    ]
    files = [LeadFileInput(**item) for item in data.get("files", [])]
    description = "\n".join(item.value_text or "" for item in answers if item.value_text).strip()
    payload = LeadCreateInput(
        user_id=current_user.id,
        category_id=data["category_id"],
        submission_key=data.get("submission_key"),
        title=data["category_title"],
        description=description or data["category_title"],
        contact_name=current_user.first_name,
        contact_phone=data.get("contact_phone") or data.get("contact"),
        contact_username=data.get("contact_username") or current_user.username,
        answers=answers,
        files=files,
        source=data.get("source", "bot"),
    )
    service = LeadService(session, get_settings())
    try:
        lead = await service.create_lead(payload)
    except (AppError, ValidationError) as exc:
        await callback.message.answer(f"Не получилось создать заявку: {exc}")
        return
    if getattr(lead, "created_now", True):
        notifier = NotificationService(callback.bot, get_settings())
        await notifier.notify_new_lead(lead)
    # Render LEAD_DONE in the root. Reset nav_stack to just [main_menu] so when
    # the user proceeds (📋 Мои заявки / 📝 Ещё заявка / 🏠 Меню) the next
    # screen has a real Back button instead of orphan navigation.
    await state.set_state(None)
    await state.update_data(nav_stack=[MAIN_MENU_SCREEN_ID])
    screen = render_lead_done(content=content, public_id=lead.public_id)
    await render_screen(
        bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen
    )


# ============= Step 5b: edit individual answers from confirm =============


async def _render_edit_answers_list(
    *,
    bot,
    chat_id: int,
    state: FSMContext,
    content: ContentService,
) -> None:
    data = await state.get_data()
    stack = await get_stack(state)
    screen = render_lead_edit_answers(content=content, draft=data, stack=stack)
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


@router.callback_query(LeadEditAnswerCallback.filter())
async def on_edit_answers_action(
    callback: CallbackQuery,
    callback_data: LeadEditAnswerCallback,
    state: FSMContext,
    content: ContentService,
) -> None:
    """Handle taps on the edit-answers list: pick one answer or confirm done."""
    data = await state.get_data()
    answers = list(data.get("answers") or [])
    questions = list(data.get("questions") or [])

    if callback_data.action == "done":
        await pop(state)  # leave edit_answers screen, back to confirm
        await state.set_state(LeadFormState.confirming)
        stack = await get_stack(state)
        data = await state.get_data()
        screen = render_lead_confirm(content=content, draft=data, stack=stack)
        await render_screen(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            screen=screen,
        )
        await callback.answer()
        return

    # action == "pick"
    index = callback_data.index
    if index < 0 or index >= len(answers) or index >= len(questions):
        await callback.answer("Вопрос не найден.", show_alert=True)
        return
    # Reuse the existing question renderer but stay on edit_answers in the stack
    # (we don't push lead_question — the user returns here after answering).
    await state.update_data(editing_index=index, question_index=index)
    await state.set_state(LeadFormState.editing_one_answer)
    stack = await get_stack(state)
    screen = render_lead_question(
        content=content,
        question=questions[index],
        index=index,
        total=len(questions),
        stack=stack,
    )
    await render_screen(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        screen=screen,
    )
    await callback.answer()


async def _persist_edited_answer(
    *,
    bot,
    chat_id: int,
    state: FSMContext,
    content: ContentService,
    value_text: str,
) -> None:
    """Overwrite the i-th answer in place, then re-show the edit-answers list."""
    data = await state.get_data()
    answers = list(data.get("answers") or [])
    questions = list(data.get("questions") or [])
    index = int(data.get("editing_index", -1))
    if index < 0 or index >= len(answers) or index >= len(questions):
        # Defensive: state desynced; bounce to confirm.
        await state.set_state(LeadFormState.confirming)
        return
    question = questions[index]
    answers[index] = {
        "question_id": question["id"],
        "key": question["key"],
        "question_text": question["text"],
        "value_text": value_text,
    }
    await state.update_data(answers=answers, editing_index=None)
    await state.set_state(LeadFormState.editing_one_answer)
    # Return user to the edit-answers list so they can pick another to edit
    # or press ✅ Готово.
    await _render_edit_answers_list(bot=bot, chat_id=chat_id, state=state, content=content)


@router.message(StateFilter(LeadFormState.editing_one_answer), F.text)
async def on_edit_text_answer(
    message: Message,
    state: FSMContext,
    content: ContentService,
) -> None:
    data = await state.get_data()
    questions = list(data.get("questions") or [])
    index = int(data.get("editing_index", -1))
    if index < 0 or index >= len(questions):
        await message.answer("Ошибка состояния. Откройте «Изменить ответы» заново.")
        return
    question = questions[index]
    raw = (message.text or "").strip()
    if question["required"] and not raw:
        await message.answer("Ответ обязателен. Напишите текстом.")
        return
    try:
        value_text = _normalize_answer_value(question, raw) if raw else ""
    except ValidationError:
        await message.answer(_validation_hint(question))
        return
    await _persist_edited_answer(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        content=content,
        value_text=value_text,
    )


@router.callback_query(
    StateFilter(LeadFormState.editing_one_answer),
    LeadQuestionChoiceCallback.filter(),
)
async def on_edit_choice_answer(
    callback: CallbackQuery,
    callback_data: LeadQuestionChoiceCallback,
    state: FSMContext,
    content: ContentService,
) -> None:
    data = await state.get_data()
    questions = list(data.get("questions") or [])
    index = int(data.get("editing_index", -1))
    if index < 0 or index >= len(questions):
        await callback.answer("Ошибка состояния.", show_alert=True)
        return
    options = questions[index].get("options") or []
    try:
        value_text = options[callback_data.option_index]
    except IndexError:
        await callback.answer("Вариант не найден.", show_alert=True)
        return
    await _persist_edited_answer(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        content=content,
        value_text=value_text,
    )
    await callback.answer()


@router.callback_query(
    StateFilter(LeadFormState.editing_one_answer),
    LeadQuestionSkipCallback.filter(),
)
async def on_edit_skip(
    callback: CallbackQuery,
    callback_data: LeadQuestionSkipCallback,
    state: FSMContext,
    content: ContentService,
) -> None:
    data = await state.get_data()
    questions = list(data.get("questions") or [])
    index = int(data.get("editing_index", -1))
    if index < 0 or index >= len(questions):
        await callback.answer("Ошибка состояния.", show_alert=True)
        return
    if questions[index]["required"]:
        await callback.answer("Этот вопрос обязателен.", show_alert=True)
        return
    await _persist_edited_answer(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        content=content,
        value_text="",
    )
    await callback.answer()


# ============= Fallback handlers (per-state escape from stuck) =============


@router.message(StateFilter(LeadFormState.answering_questions))
async def fallback_answering(message: Message, content: ContentService) -> None:
    await message.answer("Я жду текстовый ответ или выбор варианта. Нажмите 🚫 Отмена для выхода.")


@router.message(StateFilter(LeadFormState.uploading_files))
async def fallback_uploading_files(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        return  # Let EscapeMiddleware or commands through.
    await message.answer("Я жду фото или документ. Нажмите «Продолжить» или 🚫 Отмена.")


@router.message(StateFilter(LeadFormState.entering_contact))
async def fallback_entering_contact(message: Message) -> None:
    await message.answer("Я жду контакт (кнопкой или текстом). Нажмите 🚫 Отмена для выхода.")


@router.message(StateFilter(LeadFormState.confirming))
async def fallback_confirming(message: Message) -> None:
    await message.answer("Нажмите кнопку под сообщением, чтобы продолжить.")
