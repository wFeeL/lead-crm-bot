# Lead Bot Template

Commercial Telegram lead-management bot template for collecting requests, storing them in
PostgreSQL, notifying admins, managing statuses, and exporting leads.

## Stack

- Python 3.12
- aiogram 3
- FastAPI
- SQLAlchemy async + Alembic
- PostgreSQL + Redis
- Docker Compose
- pytest + ruff

## Quick Start

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
docker compose up -d postgres redis
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed
.venv/bin/python -m app.bot_main
```

Run the API separately:

```bash
.venv/bin/uvicorn app.main:app --reload
```

## Environment

Copy `.env.example` to `.env` and set:

- `BOT_TOKEN`: Telegram bot token.
- `ADMIN_IDS`: comma-separated Telegram IDs allowed to manage leads.
- `ADMIN_API_TOKEN`: bearer token for `/admin/*` API endpoints.
- `DATABASE_URL`: async SQLAlchemy URL.
- `REDIS_URL`: Redis URL for rate limits and health checks.

## Main Commands

```bash
.venv/bin/alembic revision --autogenerate -m "message"
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format .
docker compose up --build
```

## Features

- User flow: `/start`, menu, category selection, step-by-step lead form, contacts,
  attachments, confirmation, lead number, own lead list, cancellation of new leads.
- Admin flow: new lead notification, lead detail, status buttons, comments,
  assignment, new lead list, CSV export.
- API: health checks, Telegram webhook endpoint, admin lead endpoints.
- System: PostgreSQL migrations, Redis-backed rate limiting, structured logs,
  seed data, tests.

## Stage 1 — UX Core, Key Features & Content Layer (completed 2026-05-17)

The bot has been rebuilt on an SPA-like Screen infrastructure:
- One root message per user; nav buttons edit-in-place.
- 6 user screens: MAIN_MENU, FAQ, MY_LEADS, MY_LEAD_DETAIL, LEAD_CATEGORY/QUESTION/UPLOAD_FILES/CONTACT_PROMPT/CONFIRM/DONE, SUPPORT, SUPPORT_WRITING.
- 6 admin screens: ADMIN_MENU, LIST, DETAIL, COMMENT_PROMPT, CLOSE_REASON, ASSIGN_LIST.
- 7 statuses (added CONTACTED), 4 priorities (low/normal/high/urgent), close_reason for terminal statuses.
- Reassign between admins.
- Support → real lead via category `support` (internal).
- Repeat lead from MY_LEAD_DETAIL.
- Client cancel reason flow.
- All client-specific content in YAML profiles (`app/bot/content/<profile>/`).

### Adapting to a new client

1. `cp -r app/bot/content/default app/bot/content/<client_name>`
2. Edit YAML files (brand, texts, categories, faq, config).
3. Set `CONTENT_PROFILE=<client_name>` in `.env`.
4. `python -m app.seed` — categories and questions loaded.
5. Run as usual.

### Stage 1 implementation tags

- `stage1-step-0-content-layer` — YAML profile + ContentService.
- `stage1-step-1a-cat-internal` — migration 0003 (category.is_internal).
- `stage1-step-1-spa-foundation` — Screen/registry/render/EscapeMiddleware.
- `stage1-step-2-simple-screens` — MAIN_MENU/FAQ/MY_LEADS/SUPPORT.
- `stage1-step-3-lead-form-fsm` — lead create on Screen.
- `stage1-step-4-user-features` — repeat/support→lead/cancel reason.
- `stage1-step-4a-migration-0004` — CONTACTED + close_reason + priority.
- `stage1-step-5-admin-ui` — admin Screen flow + management.
- `stage1-step-6-refactor` — legacy cleanup.
- `stage1-step-6a-migration-0005` — indexes + cascade rules.
- `stage1-step-7-finishing-touches` — final tests + notify rewire.

