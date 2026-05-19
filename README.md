# Lead Bot Template

**Production-ready Telegram lead-management bot** — collect leads, manage them in
an admin panel, export to CSV. Built as a **resale template**: one codebase, many
clients. Switch niche by editing YAML — no Python changes required.

## Why this template

- **30-minute white-label.** Bundled with 3 ready niches (auto-service, beauty
  salon, medical clinic). Clone, edit a few YAML files, deploy.
- **SPA-like UX.** Single message per user with inline-button screens; no chat
  spam. Back / Home / Cancel navigation everywhere.
- **Admin panel inside the bot.** Filters, statuses (8), priorities (4),
  comments (internal & to client), reassignment, soft-delete, CSV, daily stats.
- **Robust by default.** Rate limiting, FSM defenses, escape commands,
  PostgreSQL migrations (8), 299 tests passing, ruff-clean.

## Stack

Python 3.12 · aiogram 3 · FastAPI · SQLAlchemy async + Alembic · PostgreSQL 17 ·
Redis 7 · Pydantic 2 · pytest · ruff · Docker Compose

---

## Quick start

```bash
make install          # create .venv + install dev deps
make env              # copy .env.example → .env
# edit .env: set BOT_TOKEN and ADMIN_IDS at minimum
make dev-up           # postgres + redis + migrate + bot + api
make dev-logs         # watch the bot logs
```

Open Telegram, find your bot, send `/start`. To get into admin mode, send
`/admin` from a Telegram user ID listed in `ADMIN_IDS`.

### Running outside Docker (development)

```bash
make install
make env
docker compose up -d postgres redis    # only data services
make migrate                            # alembic upgrade head
make seed                               # load categories from active profile
make bot                                # python -m app.bot_main
```

---

## Adapting the bot for a new client (5 minutes)

This is the core resale workflow. Each client gets their own **content profile**
under `app/bot/content/<profile>/` — five YAML files describing brand, texts,
FAQ, categories with form questions, and limits. Everything else stays untouched.

```bash
# 1. Scaffold a profile by cloning the closest bundled niche.
make new-client SLUG=acme_garage PROFILE=auto_service

# 2. Edit the YAML in app/bot/content/acme_garage/ — brand name, manager,
#    services, FAQ, status labels, close reasons. The CLI shows the file list.

# 3. Validate before deploy.
make validate-profile PROFILE=acme_garage

# 4. Activate.
echo 'CONTENT_PROFILE=acme_garage' >> .env
make seed                                # loads new categories into DB
make dev-up
```

See [`docs/CUSTOMIZATION.md`](docs/CUSTOMIZATION.md) for the full guide: every
YAML field, all question types, branding tips, common pitfalls.

### Bundled niches

| Slug              | Niche              | Categories                                       |
| ----------------- | ------------------ | ------------------------------------------------ |
| `default`         | Generic LeadBot    | Бот, сайт, консультация, другое                  |
| `auto_service`    | Автосервис         | ТО, ремонт, шиномонтаж, кузовной, другое         |
| `beauty_salon`    | Салон красоты      | Волосы, ногти, брови/ресницы, массаж, консультация |
| `medical_clinic`  | Медицинский центр  | Приём, анализы, УЗИ, вызов на дом, справки      |

Run `make profiles` for the live list.

---

## Production deployment

The repo ships two compose files:

- `docker-compose.yml` — dev (ports exposed, no resource limits).
- `docker-compose.prod.yml` — prod (no exposed db/redis, healthchecks,
  restart policies, resource limits).

```bash
# On the server:
git clone <your-fork> /opt/leadbot && cd /opt/leadbot
cp .env.example .env
# edit .env: BOT_TOKEN, ADMIN_IDS, POSTGRES_PASSWORD, CONTENT_PROFILE
make prod-up
make prod-logs
```

The API is bound to `127.0.0.1:8000` — front it with nginx / Caddy if you need
external access. See [`docs/DEPLOY.md`](docs/DEPLOY.md) for VPS setup, TLS, and
backups.

---

## Documentation

- [`docs/CUSTOMIZATION.md`](docs/CUSTOMIZATION.md) — adapt for a new client.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — codebase map and main flows.
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — production deployment guide.

---

## Common commands

```bash
make help              # list every target
make test              # run 299 tests
make lint              # ruff check + format --check
make fix               # auto-fix ruff issues + reformat
make migrate           # alembic upgrade head
make revision MSG=...  # create new alembic revision (autogenerate)
make profiles          # list content profiles
make new-client SLUG=acme   # scaffold a new client profile
```

---

## Repo layout

```
app/
  bot/
    content/<profile>/   # YAML profile per client (brand/texts/faq/categories/config)
    middlewares/         # rate-limit, db session, user, escape
    routers/             # aiogram routers (user + admin)
    screens/             # pure Screen renderers (no I/O)
    states/              # FSM state groups
    ui/                  # nav stack, back registry, render, callbacks
  core/                  # config, constants, security, exceptions
  db/                    # models, repositories, sessionmaker
  schemas/               # Pydantic models (content + API)
  scripts/               # CLI (profiles)
  services/              # business logic (leads, content, notifications, …)
  main.py                # FastAPI app
  bot_main.py            # aiogram entrypoint
migrations/              # Alembic
docs/                    # user-facing docs
tests/
  unit/                  # screens, callbacks, schemas, CLI
  integration/           # end-to-end flows against a real DB
```

---

## Selling points (talking to a client)

- Готовый бот за неделю — без разработки с нуля.
- Полностью на русском, тексты редактируются без программиста.
- Админ-панель прямо в Telegram, обучение менеджера ~30 минут.
- Соответствие 152-ФЗ: данные хранятся на твоём сервере (Россия / любая страна).
- Открытый код — нет vendor lock-in, можно дорабатывать самим.
- Все клиент-специфичные данные в YAML — обновления шаблона безболезненно
  накатываются на каждого клиента.
