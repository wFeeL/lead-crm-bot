# Architecture

A bird's-eye view of the codebase, enough to find your way to any change.

## Layers

```
┌───────────────────────────────────────────────────────────────┐
│  Telegram                                                     │
│     ↓ updates (polling / webhook)                             │
│  aiogram Dispatcher                                           │
│     ↓ middlewares (db, user, escape, rate-limit)              │
│  Routers (app/bot/routers/{user,admin}/*.py)                  │
│     ↓ call into                                               │
│  Services (app/services/*.py)         ← all business logic    │
│     ↓ use                                                     │
│  Repositories (app/db/repositories/*) ← all SQL               │
│     ↓                                                         │
│  SQLAlchemy models → PostgreSQL                               │
│                                                               │
│  Rendering: routers build a Screen via screen renderers       │
│  (app/bot/screens/*.py), then call render_screen() which      │
│  edits the user's "root message" in place (SPA-like UX).      │
└───────────────────────────────────────────────────────────────┘
```

## SPA-like UX

The bot keeps **one root message per user** and edits it on every screen
transition. No chat spam, the user always knows where they are.

Three primitives:

- **Screen** (`app/bot/ui/screen.py`) — a frozen dataclass: `{screen_id, text,
  keyboard, next_state}`. Produced by pure `render_*` functions in
  `app/bot/screens/*.py` — these take config + state and return a Screen, no
  I/O.
- **Nav stack** (`app/bot/ui/navigation.py`) — list of screen_ids in FSM data.
  `push(state, screen_id)` for moving forward, `pop()` for back.
- **render_screen** (`app/bot/ui/render.py`) — actually calls
  `bot.edit_message_text` on the root, falls back to `send_message` if the
  root is gone or `force_new=True` is passed (used for handoff moments like
  the lead summary after answers).

### Back navigation

`back_registry` (`app/bot/ui/back_registry.py`) maps each screen_id to a
back-renderer in `back_renderers.py`. The single `handle_nav` (`ui/handler.py`)
handles the back-button click for the entire app: pop the stack, look up the
new top, dispatch to its renderer. Wizard back-renderers also rewind FSM state
so the user lands in a coherent flow.

### Adding a new screen

1. Create `app/bot/screens/my_screen.py` with `MY_SCREEN_ID = "my_screen"`,
   a `CallbackData` subclass (optional), and a `render_my_screen(...) -> Screen`.
2. In your router handler: `push(state, MY_SCREEN_ID)`, then `render_screen(...)`.
3. Register a back-renderer in `back_renderers.py` so the back button works.

## FSM

Two `StatesGroup` namespaces:

- `LeadFormState` (`app/bot/states/lead.py`) — the client-side lead-creation
  wizard: `choosing_category` → `answering_questions` → `uploading_files` →
  `entering_contact` → `confirming` → `editing_one_answer` (when editing).
- `AdminFlowState` (`app/bot/states/admin_flow.py`) — admin sub-flows:
  `writing_internal_comment`, `writing_client_reply`, `writing_close_reason`.
- `MyLeadCancelState` (`app/bot/states/cancel.py`) — client typing custom
  cancel reason.

### FSM defenses

- `EscapeMiddleware` (`app/bot/middlewares/escape.py`) — `/start`, `/menu`,
  `/cancel` clear state and rerender MAIN_MENU. Survives any stuck wizard.
- Per-state fallback handlers in `lead_create.py` give a hint when the user
  sends an unexpected message type in the middle of the wizard.
- `is_root_message` guard (`app/bot/ui/guards.py`) — discards callbacks from
  stale messages so a user who scrolled up and tapped an old button can't
  break state.
- `@validate_question_context` decorator — checks the lead's current
  question matches the callback before processing it.

## Content layer

`app/bot/content/<profile>/` — five YAML files (`brand`, `texts`, `faq`,
`categories`, `config`) loaded at startup by `ContentService.load()`
(`app/services/content.py`) into a `ContentBundle` (`app/schemas/content.py`).
The bundle is injected into routers via the aiogram middleware data dict
(`content` key).

`Settings.content_profile` (default `"default"`) selects which directory to
load. Switching clients = switching the env var.

`ContentService.text("main_menu.title", count=3)` is the dotted-key lookup
helper for nested string templates in `texts.yaml`.

## Database

- **Models** in `app/db/models/`:
  - `User`, `Lead`, `LeadAnswer`, `LeadFile`, `LeadComment`, `LeadEvent`,
    `LeadCategory`, `LeadForm`, `LeadQuestion`.
- **Repositories** in `app/db/repositories/`:
  - `LeadRepository` — list with filters, soft-delete, status_counts, hot_count.
  - `UserRepository`, `FormRepository`.
- **Migrations** in `migrations/versions/` (Alembic):
  - `0001_initial` — base tables.
  - `0002_add_lead_submission_key` — idempotency key for lead creation.
  - `0003_add_category_is_internal` — `categories.is_internal`.
  - `0004_status_close_priority` — added CONTACTED, close_reason, priority.
  - `0005_indexes_and_cascades` — hot-path indexes + ON DELETE rules.

## Notifications

`NotificationService` (`app/services/notifications.py`) — broadcasts new
leads to `ADMIN_IDS` and `MANAGER_GROUP_ID`, sends status-change notifications
back to the client, sends comment-to-client when an admin clicks "Ответить
клиенту".

The new-lead message includes an inline button "Открыть в боте" that pushes
the admin into the lead-detail screen.

## Soft-delete

Admin can `🗑 Удалить заявку` (lead detail → confirm). Lead gets
`status='deleted'`, an `LEAD_DELETED` event is logged, and `HIDDEN_STATUSES`
filtering removes it from every list query (client and admin). Rows stay in
the DB for audit.

## Testing

- **Unit** (`tests/unit/`) — screen renderers, callbacks, schemas, CLI,
  back registry, navigation.
- **Integration** (`tests/integration/`) — full flows against a real
  SQLAlchemy session (SQLite for speed, but model code is dialect-agnostic
  so PG passes too — verified by `make prod-up`).

Run `make test` — 389 tests, ~6 seconds.

## File-loading order at startup

```
app/bot_main.py
  → Settings (.env)
  → ContentService.load(content/<CONTENT_PROFILE>) → ContentBundle
  → create_bot(settings) + create_dispatcher(settings, redis)
       → middlewares: db, user, escape, rate-limit
       → routers: nav, menu, faq, support, my_leads, lead_create, admin_menu, start
       → register_all() — installs back-renderers
  → start polling
```

## Where to find things (cheatsheet)

| You want to                                | Look in                                             |
| ------------------------------------------ | --------------------------------------------------- |
| Change a screen's layout                   | `app/bot/screens/<screen>.py`                       |
| Add a new menu button                      | `app/bot/screens/main_menu.py` + `routers/user/menu.py` |
| Change wizard validation                   | `app/bot/routers/user/lead_create.py:_normalize_answer_value` |
| Add a new lead status                      | `app/core/constants.py:LeadStatus` + `texts.yaml` + a migration |
| Change admin filter list                   | `app/bot/screens/admin_menu.py` + `admin/menu.py:on_admin_menu_action` |
| Add a new content field                    | `app/schemas/content.py` (pydantic) + `app/services/content.py` (loader) + YAML |
| Add a new DB column                        | `app/db/models/*` + `make revision MSG=...` + edit migration |
| Add a new test                             | `tests/unit/` for renderers, `tests/integration/` for flows |
