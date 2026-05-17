# Step 3 — Lead Form FSM on Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Переписать существующий lead-create flow (518-строчный `app/bot/routers/user/lead_create.py`) на Screen-based SPA-инфраструктуру. После Step 3 пользователь оставляет заявку в одном root-сообщении с консистентной навигацией и защитой от FSM-залипаний.

**Architecture:** 6 экранов-renderer'ов (LEAD_CATEGORY, LEAD_QUESTION, LEAD_UPLOAD_FILES, LEAD_CONTACT_PROMPT, LEAD_CONFIRM, LEAD_DONE) + thin handler-роутер. Reply-keyboard (контакт-кнопка, фото) — исключение из SPA: на её время inline-клавиатура root-сообщения скрывается. Декоратор `@validate_question_context` устраняет дублирование в 3 хендлерах. Per-state fallback handlers ловят невалидный ввод без выбивания пользователя из FSM.

**Tech Stack:** existing ContentService (category.title из YAML), LeadService.create_lead, validators (phone/email/date/etc.), Screen/registry/render.

**Spec sections:** «Каталог экранов → LEAD_*», «FSM Lead-формы», «Stale-callback guard», «Валидация и валидаторы».

---

## File Structure

**Create:**
- `app/bot/screens/lead_category.py` — `render_lead_category(content, categories, stack)`
- `app/bot/screens/lead_question.py` — `render_lead_question(content, question, index, total, stack)`
- `app/bot/screens/lead_files.py` — `render_lead_upload_files(content, files, max_files, stack)`
- `app/bot/screens/lead_contact.py` — `render_lead_contact_prompt(content, stack)` (inline) + helper for the reply-keyboard prompt
- `app/bot/screens/lead_confirm.py` — `render_lead_confirm(content, draft, stack)`
- `app/bot/screens/lead_done.py` — `render_lead_done(content, public_id)`
- `app/bot/ui/validate.py` — `@validate_question_context` decorator
- `app/bot/routers/user/lead_create.py` — REWRITTEN (old version backed up implicitly via git)
- Tests: `tests/unit/test_screens_lead_*.py`, `tests/integration/test_lead_create_flow.py`

**Modify:**
- `app/bot/routers/user/menu.py` — `create_lead` action: push `LEAD_CATEGORY`, render the screen instead of the "Step 3 placeholder" alert
- `app/bot/create.py` — order unchanged but the rewritten `lead_create.router` keeps its slot

**Untouched:**
- `app/bot/states/lead.py` — `LeadFormState` already correct
- `app/bot/keyboards/builders.py` — still imported by admin router; cleanup in Step 6
- `app/services/leads.py` and `validators.py` — no signature changes
- `app/services/notifications.py` — no changes

---

## FSM data contract (extends Step 2's)

```python
{
  "root_message_id": int,
  "nav_stack": list[str],

  # Draft created on LEAD_CATEGORY selection:
  "submission_key": str,
  "category_id": int,
  "category_title": str,
  "category_slug": str,
  "questions": list[dict],     # serialized via _serialize_question (kept from old code)
  "question_index": int,
  "answers": list[dict],       # [{question_id, key, question_text, value_text}]
  "files": list[dict],         # [{telegram_file_id, file_unique_id, file_type, ...}]
  "contact": str | None,
  "contact_phone": str | None,
  "contact_username": str | None,
}
```

After successful submit: full FSM cleared.

---

## Batch 1 — Screen renderers

Each renderer is sync pure function returning `Screen`. They use ContentService for status/priority labels and `nav_footer` for the nav row.

### Task 3.1 — `LEAD_CATEGORY` renderer + CategoryCallback (new namespace)

**Files:**
- Create: `app/bot/screens/lead_category.py`
- Create: `tests/unit/test_screens_lead_category.py`

Renderer:

```python
# app/bot/screens/lead_category.py
from collections.abc import Sequence
from typing import Any

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

LEAD_CATEGORY_SCREEN_ID = "lead_category"


class LeadCategoryCallback(CallbackData, prefix="lead_cat"):
    slug: str


def render_lead_category(
    *,
    content: ContentService,
    categories: list[Any],
    stack: Sequence[str],
) -> Screen:
    """Show the list of (non-internal) categories."""
    if not categories:
        text = "Категории не настроены. Обратитесь к администратору."
        keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
        return Screen(screen_id=LEAD_CATEGORY_SCREEN_ID, text=text, keyboard=keyboard)

    text = "📝 <b>Новая заявка</b>\n\nВыберите категорию:"
    extra = [
        [
            InlineKeyboardButton(
                text=category.title,
                callback_data=LeadCategoryCallback(slug=category.slug).pack(),
            )
        ]
        for category in categories
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=LEAD_CATEGORY_SCREEN_ID, text=text, keyboard=keyboard)
```

Tests verify: empty categories list shows placeholder text; non-empty list creates one button per category; nav footer present; buttons callback_data starts with `lead_cat:`.

Commit: `feat(screens): render_lead_category + LeadCategoryCallback`

### Task 3.2 — `LEAD_QUESTION` renderer + Question callbacks

**Files:**
- Create: `app/bot/screens/lead_question.py`
- Create: `tests/unit/test_screens_lead_question.py`

Renderer logic:
- Text: `f"Вопрос {index + 1}/{total}\n\n{question.text}"`. If question is optional, append `"\n\n_Можно нажать «Пропустить»._"`.
- Extra rows:
  - For `choice` type: one button per option, `LeadQuestionChoiceCallback(question_id, option_index)`.
  - Plus optional `↪ Пропустить` row when `required=False` via `LeadQuestionSkipCallback(question_id)`.
  - Plus `⬅ Назад к предыдущему` row when `index > 0` via `LeadQuestionBackCallback(question_id)`.

```python
class LeadQuestionChoiceCallback(CallbackData, prefix="lq_choice"):
    question_id: int
    option_index: int

class LeadQuestionSkipCallback(CallbackData, prefix="lq_skip"):
    question_id: int

class LeadQuestionBackCallback(CallbackData, prefix="lq_back"):
    question_id: int
```

Note: nav-footer's universal `nav:back` would also work, but we use `lq_back` to mean "back to the previous question" (different semantic from "back to previous screen").

Tests: required question has no skip button; choice with options creates choice rows; back button visible when index > 0; callback_data namespaces are correct.

Commit: `feat(screens): render_lead_question with skip/back/choice callbacks`

### Task 3.3 — `LEAD_UPLOAD_FILES` renderer + LeadFilesCallback

**Files:**
- Create: `app/bot/screens/lead_files.py`
- Create: `tests/unit/test_screens_lead_files.py`

Renderer:
- Text: `f"📎 Файлы\n\nЗагружено {len(files)}/{max_files}.\n\nПришлите фото/документ или нажмите «Продолжить»."` + list of file_names if any.
- Extra rows: `[➡ Продолжить]`, `[🗑 Удалить последний]` if files else hidden, `[⬅ Назад к ответам]`.

```python
class LeadFilesCallback(CallbackData, prefix="lead_files"):
    action: Literal["continue", "delete_last", "back_to_questions"]
```

Tests: counts in text, no delete button when empty, all actions present when has files.

Commit: `feat(screens): render_lead_upload_files with counter and delete_last`

### Task 3.4 — `LEAD_CONTACT_PROMPT` renderer + reply-keyboard helper

**Files:**
- Create: `app/bot/screens/lead_contact.py`
- Create: `tests/unit/test_screens_lead_contact.py`

Two functions:

1. `render_lead_contact_prompt(content, stack)` returns a Screen with text "📞 Оставьте контакт..." and the nav footer (no contact-specific buttons — phone is sent via reply-keyboard).
2. `make_contact_reply_keyboard()` returns a `ReplyKeyboardMarkup` with a single "📞 Отправить номер" button (`request_contact=True`) — used by the handler in a separate message.

Tests: screen has nav footer, reply-keyboard has request_contact=True button.

Commit: `feat(screens): render_lead_contact_prompt + reply-keyboard helper`

### Task 3.5 — `LEAD_CONFIRM` renderer + LeadConfirmCallback

**Files:**
- Create: `app/bot/screens/lead_confirm.py`
- Create: `tests/unit/test_screens_lead_confirm.py`

Renderer takes `draft` dict (the FSM data slice) and formats a summary. Buttons: `[✅ Отправить] [✏ Изменить ответы] [➕ Добавить файл]`.

```python
class LeadConfirmCallback(CallbackData, prefix="lead_confirm"):
    action: Literal["submit", "edit_answers", "add_file"]
```

Tests: text includes category title, contact, answer count, file count; all 3 buttons present.

Commit: `feat(screens): render_lead_confirm with submit/edit/add_file`

### Task 3.6 — `LEAD_DONE` renderer

**Files:**
- Create: `app/bot/screens/lead_done.py`
- Create: `tests/unit/test_screens_lead_done.py`

Renderer:
- Text: `f"✅ Заявка №{public_id} принята!\n\nМенеджер свяжется в течение {eta} часов.\nСтатус — в «Мои заявки»."`
- Buttons: `[📋 Мои заявки] [🏠 Меню]` (no Back).

Use ContentService for `eta_response_hours` from `brand.yaml` and `lead_done.title` / `lead_done.body` from `texts.yaml` if available — else fallback to inline strings.

Test: text contains public_id and eta value; "Мои заявки" and "Меню" buttons.

Commit: `feat(screens): render_lead_done`

---

## Batch 2 — Decorator + handler core

### Task 3.7 — `@validate_question_context` decorator

**Files:**
- Create: `app/bot/ui/validate.py`
- Create: `tests/unit/test_ui_validate.py`

Implements the dup-eliminator. Handler receives `callback`, `callback_data`, `state`. Decorator:
1. Reads `state.get_data()` for `questions` and `question_index`.
2. Compares `callback_data.question_id` to `questions[question_index]["id"]`.
3. If mismatch: `await callback.answer("Этот шаг уже неактуален.", show_alert=True)` and short-circuit.
4. If match: pass `current_question` into the handler as a kwarg.

```python
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
```

Tests: matches → handler called with `current_question` kwarg; mismatch → alert + no call; empty questions → alert + no call.

Commit: `feat(ui): @validate_question_context decorator`

---

## Batch 3 — Handler core (the new lead_create.py)

This is the largest task — replace the entire `app/bot/routers/user/lead_create.py` with a Screen-based version. Implementer should keep helper functions (`_normalize_options`, `_serialize_question`, `_normalize_answer_value`, `_validation_hint`, `_file_from_message`) — they are unchanged.

### Task 3.8 — New lead_create.py with Screen handlers

**Files:**
- Modify (full rewrite): `app/bot/routers/user/lead_create.py`
- Modify: `app/bot/routers/user/menu.py` — `create_lead` action now wires to lead_create entry point instead of alerting "Step 3"

Outline of the new `lead_create.py`:

```python
from typing import Any
from uuid import uuid4

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.screens.lead_category import (
    LEAD_CATEGORY_SCREEN_ID, LeadCategoryCallback, render_lead_category,
)
from app.bot.screens.lead_question import (
    LEAD_QUESTION_SCREEN_ID, LeadQuestionBackCallback, LeadQuestionChoiceCallback,
    LeadQuestionSkipCallback, render_lead_question,
)
from app.bot.screens.lead_files import (
    LEAD_UPLOAD_FILES_SCREEN_ID, LeadFilesCallback, render_lead_upload_files,
)
from app.bot.screens.lead_contact import (
    LEAD_CONTACT_PROMPT_SCREEN_ID, make_contact_reply_keyboard, render_lead_contact_prompt,
)
from app.bot.screens.lead_confirm import (
    LEAD_CONFIRM_SCREEN_ID, LeadConfirmCallback, render_lead_confirm,
)
from app.bot.screens.lead_done import LEAD_DONE_SCREEN_ID, render_lead_done
from app.bot.states.lead import LeadFormState
from app.bot.ui.navigation import get_stack, push
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
    validate_date, validate_email, validate_number, validate_phone, validate_time,
)

router = Router(name="lead_create")


# ============= Helper functions (preserved from old code) =============

def _normalize_options(raw_options: Any) -> list[str]:
    """Copy from old lead_create.py:44-59."""
    # ... keep identical implementation


def _serialize_question(question) -> dict[str, Any]:
    """Copy from old lead_create.py:62-70."""
    # ... keep identical implementation


def _normalize_answer_value(question: dict[str, Any], raw_text: str) -> str:
    """Copy from old lead_create.py:105-124."""
    # ... keep identical implementation


def _validation_hint(question: dict[str, Any]) -> str:
    """Copy from old lead_create.py:127-136."""
    # ... keep identical implementation


def _file_from_message(message: Message) -> dict[str, Any] | None:
    """Copy from old lead_create.py:330-351."""
    # ... keep identical implementation


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
    categories = await repo.list_categories()  # include_internal=False default
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
        content=content, question=question, index=index, total=len(questions), stack=stack,
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
        bot=message.bot, chat_id=message.chat.id, state=state, content=content, value_text=value_text,
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
        bot=callback.bot, chat_id=callback.message.chat.id,
        state=state, content=content, value_text="",
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
        bot=callback.bot, chat_id=callback.message.chat.id,
        state=state, content=content, value_text=value_text,
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
    answers.append({
        "question_id": question["id"],
        "key": question["key"],
        "question_text": question["text"],
        "value_text": value_text,
    })
    index += 1
    await state.update_data(answers=answers, question_index=index)
    if index >= len(questions):
        await state.set_state(LeadFormState.uploading_files)
        await push(state, LEAD_UPLOAD_FILES_SCREEN_ID)
        stack = await get_stack(state)
        files = (await state.get_data()).get("files", [])
        screen = render_lead_upload_files(
            content=content, files=files,
            max_files=get_settings().max_files_per_lead, stack=stack,
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
        content=content, files=files, max_files=settings.max_files_per_lead, stack=stack,
    )
    await render_screen(bot=message.bot, chat_id=message.chat.id, state=state, screen=screen)


@router.callback_query(
    StateFilter(LeadFormState.uploading_files), LeadFilesCallback.filter(),
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
                content=content, files=files, max_files=settings.max_files_per_lead, stack=stack,
            )
            await render_screen(
                bot=callback.bot, chat_id=callback.message.chat.id,
                state=state, screen=screen,
            )
    elif callback_data.action == "back_to_questions":
        # Go back to last answered question.
        answers = data.get("answers", [])
        if answers:
            answers.pop()
            await state.update_data(answers=answers, question_index=len(answers))
        await state.set_state(LeadFormState.answering_questions)
        # Pop the upload-files screen from stack.
        from app.bot.ui.navigation import pop
        await pop(state)
        await _render_current_question(
            callback.bot, callback.message.chat.id, state, content,
        )
    elif callback_data.action == "continue":
        # Move to contact prompt.
        await state.set_state(LeadFormState.entering_contact)
        await push(state, LEAD_CONTACT_PROMPT_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_lead_contact_prompt(content=content, stack=stack)
        await render_screen(
            bot=callback.bot, chat_id=callback.message.chat.id,
            state=state, screen=screen,
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
    await render_screen(bot=message.bot, chat_id=message.chat.id, state=state, screen=screen)


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
        # Go back to last question.
        data = await state.get_data()
        answers = data.get("answers", [])
        if answers:
            answers.pop()
            await state.update_data(answers=answers, question_index=len(answers))
        await state.set_state(LeadFormState.answering_questions)
        from app.bot.ui.navigation import pop
        await pop(state)  # leave confirm
        await _render_current_question(
            callback.bot, callback.message.chat.id, state, content,
        )
        await callback.answer()
    elif callback_data.action == "add_file":
        await state.set_state(LeadFormState.uploading_files)
        from app.bot.ui.navigation import pop
        await pop(state)  # leave confirm
        data = await state.get_data()
        settings = get_settings()
        stack = await get_stack(state)
        screen = render_lead_upload_files(
            content=content, files=data.get("files", []),
            max_files=settings.max_files_per_lead, stack=stack,
        )
        await render_screen(
            bot=callback.bot, chat_id=callback.message.chat.id,
            state=state, screen=screen,
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
    )
    service = LeadService(session, get_settings())
    try:
        lead = await service.create_lead(payload)
    except (AppError, ValidationError) as exc:
        await callback.message.answer(f"Не получилось создать заявку: {exc}")
        return
    if getattr(lead, "created_now", True):
        notifier = NotificationService(callback.bot, get_settings())
        # Pass None for reply_markup — admin keyboard rewrite is Step 5.
        await notifier.notify_new_lead(lead)
    # Render LEAD_DONE in the root.
    await state.set_state(None)
    await state.update_data(nav_stack=[])  # done — back to MAIN_MENU manually if user chooses.
    stack = ["lead_done"]
    screen = render_lead_done(content=content, public_id=lead.public_id)
    await render_screen(bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen)


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
```

> Note: `start_lead_create` is exported and called from `menu.py`. Update `menu.py`'s `create_lead` branch:

```python
    if callback_data.action == "create_lead":
        from app.bot.routers.user.lead_create import start_lead_create

        await start_lead_create(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            state=state,
            session=session,
            content=content,
        )
        await callback.answer()
        return
```

> Note: F filter (`F.text`, `F.photo`) needs `from aiogram import F` import.

Commit: `feat(bot): rewrite lead_create on Screen infrastructure with fallback handlers`

---

## Batch 4 — Integration tests

### Task 3.9 — End-to-end FSM test for lead creation

**Files:**
- Create: `tests/integration/test_lead_create_flow.py`

Cover:
1. Happy path: start → pick category → answer 3 questions → continue files → text contact → confirm → submit. Verify lead created in DB, notification mock called.
2. Cancel mid-flow: start → pick category → answer 1 → tap 🚫 Отмена → FSM cleared, MAIN_MENU rendered (test via mocked bot).
3. Edit answers from confirm: start → ... → confirm → edit answers → goes back to last question.
4. Skip optional question: setup a form with `required=False` question, answer it via skip.
5. Validation error: phone question, send "abc" → bot replies hint, state unchanged.
6. Fallback handler: in answering_questions, send a photo (no text) → fallback responds, no state change.

Each test uses `session` fixture (in-memory SQLite), seeds default profile via `ensure_seed_data`, creates a user, sets up FSM state with `root_message_id` pre-populated, invokes the relevant handler functions directly with mocked bot/message.

Commit: `test(bot): integration tests for lead-create FSM flow`

---

## Step 3 Completion Checklist

- [ ] `.venv/bin/pytest -q` — all green.
- [ ] `.venv/bin/ruff check .` — clean.
- [ ] 6 new renderer files in `app/bot/screens/`.
- [ ] `app/bot/ui/validate.py` exists.
- [ ] `app/bot/routers/user/lead_create.py` rewritten (no more `MenuCallback`, `FlowCallback`, `QuestionSkipCallback`).
- [ ] `menu.py` `create_lead` branch wires to `start_lead_create` (no more "Step 3 placeholder" alert).
- [ ] Per-state fallback handlers exist for `answering_questions`, `uploading_files`, `entering_contact`, `confirming`.
- [ ] `@validate_question_context` used on 3 question handlers.
- [ ] Integration tests cover happy path + cancel + edit + skip + validation + fallback.

Tag: `stage1-step-3-lead-form-fsm`.

## Out of scope

- Removing `app/bot/keyboards/builders.py` and unused MenuCallback/FlowCallback/etc. — Step 6.
- Admin lead-card keyboard rewrite — Step 5 (currently `notify_new_lead` called without `reply_markup`).
- `repeat lead` feature — Step 4.
