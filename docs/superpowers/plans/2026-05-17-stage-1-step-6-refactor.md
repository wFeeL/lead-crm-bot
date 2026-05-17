# Step 6 — Refactoring (Legacy Cleanup) Implementation Plan

**Goal:** Удалить legacy-код, который заменён на Screen-инфраструктуру в Step 1-5. После Step 6 нет дублирования между старыми и новыми колбэками/клавиатурами/хендлерами.

**Audit summary** (что обнаружено grep):
- `app/bot/texts/user.py` — старые строковые константы, заменены на `texts.yaml`
- `app/services/forms.py:LEAD_FORM_DEFINITIONS` — заменено на `categories.yaml`
- `app/bot/keyboards/builders.py` — все builders заменены на render_* функции
- `app/bot/utils.py` — `remove_inline_keyboard`/`replace_message_text` использовались только legacy
- `app/bot/routers/admin/leads.py` — заменён на `admin/menu.py` (Step 5)
- `app/bot/states/lead.py:AdminCommentState` — заменён на `AdminFlowState` в `admin_flow.py`
- `tests/unit/test_formatting_and_keyboards.py` — тестирует удаляемые builders

Также:
- `app/services/formatting.py` — есть N+1 на LeadComment.admin: добавить `selectinload`.

---

## Tasks

### Task 6.1 — Remove legacy admin router

Files:
- Delete: `app/bot/routers/admin/leads.py` (380 lines)
- Modify: `app/bot/create.py` — remove `from app.bot.routers.admin import leads as admin_leads` and `dispatcher.include_router(admin_leads.router)`

Run `.venv/bin/pytest -q`. The legacy `/new`, `/leads`, `/leads_user`, `/leads_date`, `/export` commands will stop working — only `/admin` Screen flow remains. CSV export is still available via `/admin → 📤 CSV`. Standalone `/export` command is gone.

`tests/integration/test_admin_api.py` might use these — check. If tests reference legacy admin handlers, delete those tests.

Commit: `refactor(bot): remove legacy admin router`

### Task 6.2 — Remove AdminCommentState

In `app/bot/states/lead.py`, delete the `AdminCommentState` class. Replace with a brief comment that AdminFlowState now lives in `app/bot/states/admin_flow.py`.

If `app/bot/states/lead.py` only contained `LeadFormState` + `AdminCommentState`, the file becomes shorter:

```python
from aiogram.fsm.state import State, StatesGroup


class LeadFormState(StatesGroup):
    choosing_category = State()
    answering_questions = State()
    uploading_files = State()
    entering_contact = State()
    confirming = State()
```

Verify no remaining imports of `AdminCommentState` after Task 6.1 (the only importer was legacy `admin/leads.py`).

Commit: `refactor(states): remove AdminCommentState`

### Task 6.3 — Remove keyboards/builders.py and bot/utils.py

After Task 6.1, no production code imports from these. Verify with grep first.

Files:
- Delete: `app/bot/keyboards/builders.py`
- Delete: `app/bot/utils.py`
- Modify: `tests/unit/test_formatting_and_keyboards.py` — delete the file (tests legacy builders) OR strip down to only formatting tests if `format_lead_summary`/`format_public_lead_line` are tested there.

Run `pytest`. Anything that breaks = needs cleanup. Most likely zero breakages.

Commit: `refactor(bot): remove keyboards/builders.py and bot/utils.py`

### Task 6.4 — Remove LEAD_FORM_DEFINITIONS and texts/user.py

After Step 0, `ensure_seed_data` reads from `ContentBundle`. `LEAD_FORM_DEFINITIONS` is dead.

Files:
- Modify: `app/services/forms.py` — delete `LEAD_FORM_DEFINITIONS` list (lines 6-90 ish). File becomes ~30 lines with just `ensure_seed_data`.
- Delete: `app/bot/texts/user.py`
- Delete (likely): `app/bot/texts/__init__.py` — if only used by `user.py`. Check first.

Run `pytest`. Update any test that imported `LEAD_FORM_DEFINITIONS` or `START_TEXT`/`SUPPORT_TEXT`/`FAQ_TEXT`.

Commit: `refactor(content): remove LEAD_FORM_DEFINITIONS and texts/user.py`

### Task 6.5 — Fix N+1 in formatting.py

In `app/services/formatting.py`, `format_lead_summary` iterates `lead.comments` and may access `comment.admin` lazily, causing N+1. Check the file. If `comments.admin` is accessed without `selectinload`, fix `_lead_options()` in `app/db/repositories/leads.py` to include:

```python
from sqlalchemy.orm import selectinload

def _lead_options(self):
    return (
        selectinload(Lead.answers),
        selectinload(Lead.files),
        selectinload(Lead.comments).selectinload(LeadComment.admin),
        selectinload(Lead.category),
        selectinload(Lead.user),
        selectinload(Lead.assigned_admin),  # NEW — used by admin_lead_detail screen
    )
```

If `_lead_options` doesn't exist, find `LeadRepository.get` and add the selectinload chain there.

Test: existing tests should still pass. Add a small test that loading a lead with comments doesn't issue extra queries (use SQLAlchemy logging or count) — OR just verify the selectinload appears.

Commit: `perf(db): selectinload comments.admin and assigned_admin to fix N+1`

---

## Step 6 Completion Checklist

- [ ] `.venv/bin/pytest -q` — green.
- [ ] `.venv/bin/ruff check .` — clean.
- [ ] `app/bot/keyboards/builders.py` deleted.
- [ ] `app/bot/utils.py` deleted.
- [ ] `app/bot/texts/user.py` deleted (and `__init__.py` if standalone).
- [ ] `app/bot/routers/admin/leads.py` deleted.
- [ ] `LEAD_FORM_DEFINITIONS` removed from `forms.py`.
- [ ] `AdminCommentState` removed from `states/lead.py`.
- [ ] N+1 selectinload added.

Tag: `stage1-step-6-refactor`.
