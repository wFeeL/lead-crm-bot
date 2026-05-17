# Step 4 — User Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Завершить пользовательские фичи этапа 1: `🔁 Повторить` на карточке заявки, поддержка через категорию `support` (реальный lead), причина при отмене клиентом.

**Architecture:** Используем существующие модели + ContentService. Категория `support` добавляется в YAML (с `is_internal=true`); `LeadService.build_draft_from_lead` создаёт FSM-draft из ответов существующей заявки; `MyLeadCancelState` — отдельная FSM для выбора причины отмены.

**Spec sections:** «Повтор заявки», «Связаться с менеджером», `MY_LEAD_DETAIL.buttons.repeat`, `MyLeadCancelState`.

---

## File Structure

**Create:**
- `app/bot/screens/cancel_reason.py` — `render_cancel_reason_screen(content, lead_id, stack)`, `CancelReasonCallback`
- `app/bot/states/cancel.py` — `MyLeadCancelState`
- `tests/integration/test_repeat_lead.py`
- `tests/integration/test_support_creates_lead.py`
- `tests/integration/test_cancel_reason_flow.py`

**Modify:**
- `app/bot/content/default/categories.yaml` — add `support` category (internal=true, one long_text question)
- `app/services/leads.py` — `LeadService.build_draft_from_lead(lead_id, actor) -> dict`
- `app/bot/screens/my_leads.py` — add `🔁 Повторить` button to `render_my_lead_detail` for non-terminal statuses (NEW, IN_PROGRESS, WAITING, DONE)
- `app/bot/routers/user/my_leads.py` — handle `MyLeadDetailCallback(action="repeat")` and the cancel-with-reason flow
- `app/bot/routers/user/support.py` — replace text-only stub with `LeadService.create_lead(source='support')`

**Untouched:**
- `app/bot/screens/main_menu.py` — confirmed: no repeat button in MAIN_MENU per spec revision (only on MY_LEAD_DETAIL).
- Lead-create flow (Step 3 already covers reusing draft for "repeat").

---

## Task 4.1 — Add `support` category to YAML

**Files:** `app/bot/content/default/categories.yaml`.

Append to `default/categories.yaml`:

```yaml
- slug: support
  title: "Связь с менеджером"
  description: "Обращение в поддержку"
  internal: true
  questions:
    - key: message
      text: "Опишите ваш вопрос"
      type: long_text
      required: true
```

This category is `internal=true` so it's NOT shown in `LEAD_CATEGORY` selection but is used by the support handler.

Update `tests/integration/test_content_seed.py::test_ensure_seed_data_from_default_profile` to expect 5 categories (was 4). Update the slug-set assertion.

Commit: `feat(content): add support category to default profile`

---

## Task 4.2 — `LeadService.build_draft_from_lead`

**Files:** `app/services/leads.py`, `tests/integration/test_lead_service.py`.

Method signature:

```python
async def build_draft_from_lead(self, *, lead_id: int, actor: User) -> dict:
    """Build a FSM-draft dict from an existing lead so the user can repeat it.

    Returns a dict matching the structure stored in FSM data during lead creation:
        {
            "submission_key": <new uuid>,
            "category_id": ...,
            "category_title": ...,
            "category_slug": ...,
            "questions": [...],
            "question_index": <len(answers)>,  # past the last question, ready for files step
            "answers": [...],   # copied from source lead's answers
            "files": [],        # files NOT copied (file_id may be stale)
            "contact": <source contact>,
            "contact_phone": ...,
            "contact_username": ...,
            "source": "repeat",
        }

    Raises ValidationError if lead.user_id != actor.id.
    """
```

Implementation reads the lead with answers via `LeadRepository.get`, walks the form questions, builds the dict. Reuses `_serialize_question` from `lead_create.py` — extract it to a shared helper (or duplicate; the latter avoids a circular dep).

Simpler: serialize the questions inline in the method, no helper extraction.

Tests:
- Build draft from a real lead → returned dict has all answers, new submission_key, file list empty.
- Build draft for someone else's lead → raises ValidationError ("not owner").
- Build draft for non-existent lead_id → raises ValidationError or LeadNotFound (whichever exception exists in `app/core/exceptions.py`).

Commit: `feat(leads): LeadService.build_draft_from_lead for repeat flow`

---

## Task 4.3 — Add `🔁 Повторить` button to MY_LEAD_DETAIL + handler

**Files:** `app/bot/screens/my_leads.py`, `app/bot/routers/user/my_leads.py`.

In `app/bot/screens/my_leads.py`:
1. Add `"repeat"` to `MyLeadDetailCallback.action` Literal: `Literal["open", "cancel", "repeat"]`.
2. In `render_my_lead_detail`, add the repeat button BEFORE the cancel button (or first):

```python
    extra: list[list[InlineKeyboardButton]] = []
    if lead.status not in ("rejected", "cancelled"):
        extra.append([
            InlineKeyboardButton(
                text="🔁 Повторить",
                callback_data=MyLeadDetailCallback(action="repeat", lead_id=lead.id).pack(),
            )
        ])
    if lead.status == "new":
        extra.append([
            InlineKeyboardButton(
                text="🚫 Отменить заявку",
                callback_data=MyLeadDetailCallback(action="cancel", lead_id=lead.id).pack(),
            )
        ])
```

In `app/bot/routers/user/my_leads.py`:
1. Add `elif callback_data.action == "repeat":` branch in `handle_lead_detail_action`.
2. The branch:
   - Calls `LeadService(session, get_settings()).build_draft_from_lead(lead_id=callback_data.lead_id, actor=current_user)`. On `ValidationError`, alert + return.
   - Sets state to `LeadFormState.confirming`.
   - Updates FSM data with draft + nav_stack push `lead_confirm`.
   - Renders `LEAD_CONFIRM` screen.

Imports needed: `LeadService`, `LeadFormState`, `get_settings`, `LEAD_CONFIRM_SCREEN_ID`, `render_lead_confirm`, `push`, `get_stack`, `render_screen`, `ValidationError`.

Tests in `tests/integration/test_repeat_lead.py`:
1. Create a lead via `LeadService.create_lead`. Open MY_LEAD_DETAIL. Click `repeat`. Verify state == LeadFormState.confirming, draft contains the answers, nav_stack has `lead_confirm` on top.
2. Try to repeat someone else's lead → callback.answer with alert, state unchanged.
3. After repeat, submit (click `LeadConfirmCallback(action="submit")`) → new lead created with source="repeat" in DB.

Commit: `feat(bot): repeat lead from MY_LEAD_DETAIL via build_draft_from_lead`

---

## Task 4.4 — Support handler creates real lead

**Files:** `app/bot/routers/user/support.py`, `tests/integration/test_support_creates_lead.py`.

Replace `handle_support_message` body to create a real lead via `LeadService.create_lead` with `source="support"`. The category id is looked up via `FormRepository.get_category_by_slug("support")` (which must exist after Task 4.1).

```python
@router.message(StateFilter(SupportState.writing_message))
async def handle_support_message(
    message: Message,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, отправьте текст сообщения.")
        return

    from app.db.repositories.forms import FormRepository
    from app.schemas.lead import LeadAnswerInput, LeadCreateInput
    from app.services.leads import LeadService
    from app.core.config import get_settings
    from uuid import uuid4

    repo = FormRepository(session)
    category = await repo.get_category_by_slug("support")
    if category is None:
        # Profile missing support category — degrade gracefully.
        await message.answer("✉️ Сообщение получено. Менеджер свяжется.")
        await state.set_state(None)
        return

    form = await repo.get_active_form(category.id)
    question = form.questions[0] if form and form.questions else None

    answers = []
    if question is not None:
        answers.append(LeadAnswerInput(question_id=question.id, key=question.key, value_text=text))

    payload = LeadCreateInput(
        user_id=current_user.id,
        category_id=category.id,
        submission_key=uuid4().hex,
        title="Связь с менеджером",
        description=text,
        contact_name=current_user.first_name,
        contact_phone=current_user.phone,
        contact_username=current_user.username,
        answers=answers,
        files=[],
        source="support",
    )

    service = LeadService(session, get_settings())
    lead = await service.create_lead(payload)

    if getattr(lead, "created_now", True):
        from app.services.notifications import NotificationService
        notifier = NotificationService(message.bot, get_settings())
        await notifier.notify_new_lead(lead)

    await message.answer(f"✉️ Спасибо! Ваше обращение №{lead.public_id} отправлено менеджеру.")
    await state.set_state(None)
    await state.update_data({"root_message_id": None, "nav_stack": []})

    from app.bot.routers.user.menu import render_and_show_main_menu
    from app.db.repositories.leads import LeadRepository
    repo = LeadRepository(session)
    leads_count = await repo.count_by_user(current_user.id)
    await render_and_show_main_menu(
        bot=message.bot, chat_id=message.chat.id,
        state=state, content=content, leads_count=leads_count,
    )
```

> Note: `LeadCreateInput` needs `source` parameter. Check `app/schemas/lead.py` — if `source` isn't already a field, add it. The DB column already exists.

> Note: `LeadService.create_lead` currently sets `source` from payload. Verify in `app/services/leads.py`. If it hardcodes `source="bot"` or similar, generalize it to accept `payload.source`.

Tests in `tests/integration/test_support_creates_lead.py`:
1. Seed default profile (now with support category). User writes "помогите!" → lead created with category.slug="support", source="support".
2. Empty text → bot asks for text, no lead created.
3. After successful submit, state cleared and MAIN_MENU rendered.

Commit: `feat(bot): support handler creates real lead via LeadService`

---

## Task 4.5 — Cancel reason for client (MyLeadCancelState)

**Files:** `app/bot/states/cancel.py`, `app/bot/screens/cancel_reason.py`, `app/bot/routers/user/my_leads.py`.

Step 4 cancel-with-reason WITHOUT changing the DB schema. The client's `close_reason` will be stored later when migration 0004 (Step 4a) adds the column. For Step 4 we collect the reason and stash it in FSM until `LeadService.cancel_by_client` is enhanced to accept it.

**Two-phase approach for Step 4:**

Phase A: Show the reason prompt and accept the chosen/typed reason.
Phase B: Pass reason to `LeadService.cancel_by_client` once the method accepts it (Step 4a + a follow-up).

For Step 4, we add `reason` parameter to `LeadService.cancel_by_client` with default None — it just gets ignored until Step 4a adds the column. The signature becomes future-proof.

### State

`app/bot/states/cancel.py`:

```python
from aiogram.fsm.state import State, StatesGroup


class MyLeadCancelState(StatesGroup):
    writing_custom_reason = State()
```

### Screen

`app/bot/screens/cancel_reason.py`:

```python
from collections.abc import Sequence
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

MY_LEAD_CANCEL_REASON_SCREEN_ID = "my_lead_cancel_reason"
CUSTOM_REASON_LABEL = "Своя причина"


class CancelReasonCallback(CallbackData, prefix="cancel_reason"):
    action: Literal["pick", "custom"]
    lead_id: int
    index: int = -1  # -1 for action="custom"


def render_cancel_reason(
    *,
    content: ContentService,
    lead_id: int,
    stack: Sequence[str],
) -> Screen:
    reasons = content.texts.close_reasons.cancelled or [CUSTOM_REASON_LABEL]
    extra: list[list[InlineKeyboardButton]] = []
    for i, reason in enumerate(reasons):
        if reason == CUSTOM_REASON_LABEL:
            cb = CancelReasonCallback(action="custom", lead_id=lead_id, index=i).pack()
        else:
            cb = CancelReasonCallback(action="pick", lead_id=lead_id, index=i).pack()
        extra.append([InlineKeyboardButton(text=reason, callback_data=cb)])

    text = "🚫 <b>Отмена заявки</b>\n\nВыберите причину или укажите свою:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=MY_LEAD_CANCEL_REASON_SCREEN_ID, text=text, keyboard=keyboard)
```

### Handler additions in `my_leads.py`

- `MyLeadDetailCallback(action="cancel")` no longer immediately cancels — it pushes `MY_LEAD_CANCEL_REASON_SCREEN_ID` and renders the reason screen.
- New handler `handle_cancel_reason` for `CancelReasonCallback.filter()`:
  - `action == "pick"`: extract reason from `content.texts.close_reasons.cancelled[index]`, call `service.cancel_by_client(lead_id, actor, reason=reason)`, re-render MY_LEAD_DETAIL with updated status.
  - `action == "custom"`: set FSM state `MyLeadCancelState.writing_custom_reason`, store `lead_id` in FSM data, render a prompt screen.
- New `@router.message(StateFilter(MyLeadCancelState.writing_custom_reason))`: read text, call `cancel_by_client(reason=text)`, render MY_LEAD_DETAIL.

### LeadService.cancel_by_client signature

Add `reason: str | None = None` parameter:

```python
async def cancel_by_client(self, *, lead_id: int, actor: User, reason: str | None = None) -> Lead:
    """Cancel a lead by its owner. `reason` is stored once Step 4a adds the column.

    Currently `reason` is logged but not persisted to lead.close_reason because
    the column doesn't exist yet (added in migration 0004).
    """
    # ... existing logic ...
    # When migration 0004 lands, set `lead.close_reason = reason`.
```

Update existing callers in test files (`tests/integration/test_my_leads_flow.py::test_cancel_lead_via_callback` etc.) to use kw-arg syntax if they aren't already.

### Tests

`tests/integration/test_cancel_reason_flow.py`:
1. Cancel with predefined reason → `cancel_by_client` called with `reason="Передумал"` (or whichever is at index 0 in default profile).
2. Cancel with custom reason → FSM transitions to `writing_custom_reason`, text message accepted → reason stored.

Commit: `feat(bot): client cancel reason flow with predefined + custom`

---

## Step 4 Completion Checklist

- [ ] `support` category in `categories.yaml`.
- [ ] `LeadService.build_draft_from_lead` works (owner check + new submission_key).
- [ ] `🔁 Повторить` button visible on MY_LEAD_DETAIL for non-terminal statuses.
- [ ] Repeat handler restores draft, sets state to confirming, pushes lead_confirm.
- [ ] Support handler creates real lead with `source="support"`.
- [ ] Cancel flow: pick reason or custom → `cancel_by_client(reason=...)`.
- [ ] All tests green.
- [ ] Ruff clean.

Tag: `stage1-step-4-user-features`.

## Out of scope

- Persistence of `close_reason` to DB — Step 4a migration.
- Admin-facing reason display — Step 5.
