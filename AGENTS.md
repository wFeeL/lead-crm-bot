# Repository Guidelines

## Project Structure & Module Organization

This repository is at the scaffold/planning stage. Keep implementation aligned with the planned Python layout:

- `app/main.py`: FastAPI entry point for API routes, health checks, and webhooks.
- `app/bot_main.py`: local polling entry point for the Telegram bot.
- `app/core/`: configuration, logging, security helpers, constants, and exceptions.
- `app/db/`: SQLAlchemy async sessions, models, and repositories.
- `app/schemas/`: Pydantic schemas.
- `app/services/`: lead, notification, file, report, export, anti-spam, and CRM logic.
- `app/bot/`: aiogram routers, keyboards, FSM states, middlewares, filters, and texts.
- `app/api/`: FastAPI routers and dependencies.
- `app/tasks/`: scheduled jobs and workers.
- `migrations/`: Alembic environment and migration versions.
- `tests/`: `unit/`, `integration/`, and `bot/` tests.

`PROJECT_MEMORY.md` is ignored and should remain local planning context.

## Build, Test, and Development Commands

Use Python 3.12 with `venv + pip`.

- `python3.12 -m venv .venv`: create the local environment.
- `.venv/bin/pip install -r requirements-dev.txt`: install runtime and dev dependencies.
- `.venv/bin/uvicorn app.main:app --reload`: run FastAPI locally.
- `.venv/bin/python -m app.bot_main`: run the bot in polling mode.
- `docker compose up --build`: start API, bot, worker, PostgreSQL, and Redis.
- `.venv/bin/alembic revision --autogenerate -m "message"`: create migrations.
- `.venv/bin/alembic upgrade head`: apply migrations.
- `.venv/bin/pytest`: run the test suite.
- `.venv/bin/ruff check .` and `.venv/bin/ruff format .`: lint and format code.

## Coding Style & Naming Conventions

Target Python 3.12+. Use async code consistently for aiogram, FastAPI, SQLAlchemy, and Redis. Keep boundaries explicit: handlers call services, services call repositories, repositories own database queries. Use `snake_case` for files, modules, functions, and variables; `PascalCase` for classes and Pydantic/SQLAlchemy models. Keep bot texts under `app/bot/texts/`.

## Testing Guidelines

Use `pytest` with `pytest-asyncio`. Place business-logic tests in `tests/unit/`, database/API tests in `tests/integration/`, and aiogram handler/FSM tests in `tests/bot/`. Name files `test_*.py` and functions `test_*`. Prioritize lead creation, status transitions, validation, repositories, API filters, keyboards, and FSM cancellation/confirmation.

## Commit & Pull Request Guidelines

There is no established Git history yet. Use short imperative commit messages, preferably Conventional Commits such as `feat: add lead creation service` or `test: cover status transitions`.

Pull requests should include a summary, linked issue/task, migration notes, environment changes, and test results. Add screenshots only for user-facing bot or admin UI changes.

## Security & Configuration Tips

Never commit `.env`, bot tokens, admin IDs, database passwords, or Sentry DSNs. Keep safe defaults in `.env.example`. Validate Telegram webhook `secret_token` before processing updates in production.
