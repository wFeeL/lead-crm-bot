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

