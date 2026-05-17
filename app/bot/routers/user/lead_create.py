from typing import Any
from uuid import uuid4

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.builders import (
    CategoryCallback,
    FlowCallback,
    MenuCallback,
    QuestionBackCallback,
    QuestionChoiceCallback,
    QuestionSkipCallback,
    admin_lead_keyboard,
    confirmation_keyboard,
    contact_keyboard,
    files_keyboard,
    main_menu_keyboard,
    question_keyboard,
)
from app.bot.states.lead import LeadFormState
from app.bot.utils import remove_inline_keyboard
from app.core.config import Settings, get_settings
from app.core.constants import FileType, QuestionType
from app.core.exceptions import AppError, ValidationError
from app.db.models.user import User
from app.db.repositories.forms import FormRepository
from app.schemas.lead import LeadAnswerInput, LeadCreateInput, LeadFileInput
from app.services.leads import LeadService
from app.services.notifications import NotificationService
from app.services.validators import (
    validate_date,
    validate_email,
    validate_number,
    validate_phone,
    validate_time,
)

router = Router(name="user_lead_create")


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


async def _ask_question(target: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data["questions"]
    index = data["question_index"]
    question = questions[index]
    suffix = "" if question["required"] else "\n\nМожно нажать «Пропустить»."
    options = question["options"] if question["type"] == QuestionType.CHOICE else None
    await target.answer(
        f"{index + 1}/{len(questions)}. {question['text']}{suffix}",
        reply_markup=question_keyboard(
            required=question["required"],
            question_id=question["id"],
            options=options,
            can_go_back=index > 0,
        ),
    )


def _build_confirmation_text(data: dict[str, Any]) -> str:
    answers = data.get("answers", [])
    answer_lines = "\n".join(
        f"- {item['question_text']}: {item.get('value_text') or '-'}" for item in answers
    )
    return (
        "Проверьте заявку перед отправкой.\n\n"
        f"Категория: {data.get('category_title')}\n"
        f"Контакт: {data.get('contact')}\n"
        f"Файлов: {len(data.get('files', []))}\n\n"
        f"Ответы:\n{answer_lines or '-'}"
    )


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


async def _save_answer_and_advance(
    target: Message,
    state: FSMContext,
    *,
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
        await target.answer(
            "Прикрепите фото/файл или продолжите.",
            reply_markup=files_keyboard(),
        )
    else:
        await _ask_question(target, state)


async def _go_to_previous_question(target: Message, state: FSMContext) -> bool:
    data = await state.get_data()
    index = data["question_index"]
    answers = data.get("answers", [])
    if index <= 0:
        await target.answer("Это первый вопрос. Можно отменить заявку и начать заново.")
        return False
    index -= 1
    if answers:
        answers.pop()
    await state.update_data(answers=answers, question_index=index)
    await state.set_state(LeadFormState.answering_questions)
    await _ask_question(target, state)
    return True


@router.callback_query(MenuCallback.filter(F.action == "create"))
async def start_create_lead(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await state.clear()
    categories = await FormRepository(session).list_categories()
    if not categories:
        await callback.message.edit_text("Категории не настроены. Запустите seed-команду.")
        await callback.answer()
        return
    from app.bot.keyboards.builders import categories_keyboard

    await state.set_state(LeadFormState.choosing_category)
    await state.update_data(submission_key=uuid4().hex)
    await callback.message.edit_text(
        "Выберите категорию заявки.",
        reply_markup=categories_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(LeadFormState.choosing_category, CategoryCallback.filter())
async def choose_category(
    callback: CallbackQuery,
    callback_data: CategoryCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    repository = FormRepository(session)
    category = await repository.get_category_by_slug(callback_data.slug)
    if category is None:
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    form = await repository.get_active_form(category.id)
    if form is None or not form.questions:
        await callback.answer("Форма не настроена.", show_alert=True)
        return
    await remove_inline_keyboard(callback.message)
    await state.update_data(
        category_id=category.id,
        category_title=category.title,
        questions=[_serialize_question(question) for question in form.questions],
        question_index=0,
        answers=[],
        files=[],
    )
    await state.set_state(LeadFormState.answering_questions)
    await callback.message.answer(f"Категория: {category.title}")
    await _ask_question(callback.message, state)
    await callback.answer()


@router.callback_query(
    LeadFormState.answering_questions,
    QuestionSkipCallback.filter(),
)
async def skip_optional_question(
    callback: CallbackQuery,
    callback_data: QuestionSkipCallback,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    questions = data["questions"]
    index = data["question_index"]
    question = questions[index]
    if callback_data.question_id != question["id"]:
        await remove_inline_keyboard(callback.message)
        await callback.answer("Этот вопрос уже неактуален.", show_alert=True)
        return
    if question["required"]:
        await callback.answer("Этот вопрос обязателен.", show_alert=True)
        return
    await remove_inline_keyboard(callback.message)
    await _save_answer_and_advance(callback.message, state, value_text="")
    await callback.answer()


@router.callback_query(
    LeadFormState.answering_questions,
    QuestionChoiceCallback.filter(),
)
async def collect_choice_answer(
    callback: CallbackQuery,
    callback_data: QuestionChoiceCallback,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    questions = data["questions"]
    question = questions[data["question_index"]]
    if callback_data.question_id != question["id"]:
        await remove_inline_keyboard(callback.message)
        await callback.answer("Этот вопрос уже неактуален.", show_alert=True)
        return
    try:
        value_text = question["options"][callback_data.option_index]
    except IndexError:
        await callback.answer("Вариант не найден.", show_alert=True)
        return
    await remove_inline_keyboard(callback.message)
    await _save_answer_and_advance(callback.message, state, value_text=value_text)
    await callback.answer()


@router.callback_query(
    LeadFormState.answering_questions,
    QuestionBackCallback.filter(),
)
async def back_to_previous_question(
    callback: CallbackQuery,
    callback_data: QuestionBackCallback,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    questions = data["questions"]
    question = questions[data["question_index"]]
    if callback_data.question_id != question["id"]:
        await remove_inline_keyboard(callback.message)
        await callback.answer("Этот вопрос уже неактуален.", show_alert=True)
        return
    await remove_inline_keyboard(callback.message)
    await _go_to_previous_question(callback.message, state)
    await callback.answer()


@router.message(LeadFormState.answering_questions)
async def collect_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data["questions"]
    index = data["question_index"]
    question = questions[index]
    text = (message.text or "").strip()
    if question["required"] and not text:
        await message.answer("Ответ обязателен. Напишите текстом или выберите вариант.")
        return
    try:
        value_text = _normalize_answer_value(question, text) if text else ""
    except ValidationError:
        await message.answer(_validation_hint(question))
        return
    await _save_answer_and_advance(message, state, value_text=value_text)


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


@router.message(LeadFormState.uploading_files)
async def collect_file(
    message: Message,
    state: FSMContext,
    settings: Settings = get_settings(),
) -> None:
    file_data = _file_from_message(message)
    if file_data is None:
        await message.answer(
            "Отправьте фото/файл или нажмите «Продолжить».",
            reply_markup=files_keyboard(),
        )
        return
    data = await state.get_data()
    files = data.get("files", [])
    if len(files) >= settings.max_files_per_lead:
        await message.answer("Достигнут лимит файлов.", reply_markup=files_keyboard())
        return
    if file_data.get("size") and file_data["size"] > settings.max_file_size_bytes:
        await message.answer("Файл слишком большой.", reply_markup=files_keyboard())
        return
    files.append(file_data)
    await state.update_data(files=files)
    await message.answer(
        f"Файл добавлен. Всего файлов: {len(files)}",
        reply_markup=files_keyboard(),
    )


@router.callback_query(LeadFormState.uploading_files, FlowCallback.filter(F.action == "files_done"))
async def files_done(callback: CallbackQuery, state: FSMContext) -> None:
    await remove_inline_keyboard(callback.message)
    data = await state.get_data()
    if data.get("contact"):
        await state.set_state(LeadFormState.confirming)
        await callback.message.answer(
            _build_confirmation_text(data),
            reply_markup=confirmation_keyboard(),
        )
    else:
        await state.set_state(LeadFormState.entering_contact)
        await callback.message.answer(
            "Оставьте контакт для связи: телефон, @username или удобный способ связи.",
            reply_markup=contact_keyboard(),
        )
    await callback.answer()


@router.callback_query(LeadFormState.confirming, FlowCallback.filter(F.action == "add_file"))
async def add_file_again(callback: CallbackQuery, state: FSMContext) -> None:
    await remove_inline_keyboard(callback.message)
    await state.set_state(LeadFormState.uploading_files)
    await callback.message.answer(
        "Прикрепите фото/файл или продолжите.",
        reply_markup=files_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    LeadFormState.uploading_files,
    FlowCallback.filter(F.action == "back_to_questions"),
)
@router.callback_query(
    LeadFormState.confirming,
    FlowCallback.filter(F.action == "edit_answers"),
)
async def edit_answers(callback: CallbackQuery, state: FSMContext) -> None:
    await remove_inline_keyboard(callback.message)
    changed = await _go_to_previous_question(callback.message, state)
    await callback.answer("Вернулись к вопросам." if changed else None)


@router.message(LeadFormState.entering_contact)
async def collect_contact(message: Message, state: FSMContext) -> None:
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
            "Контакт обязателен. Напишите телефон, username или другой способ связи."
        )
        return
    updates["contact"] = contact
    await state.update_data(**updates)
    await state.set_state(LeadFormState.confirming)
    data = await state.get_data()
    await message.answer("Контакт сохранен.", reply_markup=ReplyKeyboardRemove())
    await message.answer(_build_confirmation_text(data), reply_markup=confirmation_keyboard())


@router.callback_query(FlowCallback.filter(F.action == "cancel"))
async def cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await remove_inline_keyboard(callback.message)
    await callback.message.answer(
        "Создание заявки отменено.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(LeadFormState.confirming, FlowCallback.filter(F.action == "submit"))
async def submit_lead(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
) -> None:
    await remove_inline_keyboard(callback.message)
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
    )
    service = LeadService(session, get_settings())
    try:
        lead = await service.create_lead(payload)
    except (AppError, ValidationError) as exc:
        await callback.message.answer(f"Не получилось создать заявку: {exc}")
        return
    if getattr(lead, "created_now", True):
        notifier = NotificationService(callback.bot, get_settings())
        await notifier.notify_new_lead(lead, reply_markup=admin_lead_keyboard(lead))
    await state.clear()
    await callback.message.answer(f"Ваша заявка {lead.public_id} принята.")


@router.callback_query(CategoryCallback.filter())
async def stale_category(callback: CallbackQuery) -> None:
    await remove_inline_keyboard(callback.message)
    await callback.answer("Выбор категории уже неактуален. Начните заново.", show_alert=True)


@router.callback_query(FlowCallback.filter())
async def stale_flow_callback(callback: CallbackQuery) -> None:
    await remove_inline_keyboard(callback.message)
    await callback.answer("Это действие уже неактуально.", show_alert=True)
