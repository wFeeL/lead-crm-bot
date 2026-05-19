# Production deployment guide

Target: a single client's bot on a small VPS (1 vCPU, 2 GB RAM is enough).

## Prerequisites

- Linux VPS with Docker + Docker Compose v2.
- Domain name (optional — only needed for webhook mode or external API access).
- Telegram bot token from [@BotFather](https://t.me/BotFather).
- Your client's admin Telegram user IDs (get from [@userinfobot](https://t.me/userinfobot)).

## First-time setup

```bash
# 1. Get the code onto the server.
git clone <your-fork-url> /opt/leadbot && cd /opt/leadbot

# 2. Create .env.
cp .env.example .env
vim .env   # see "Required env vars" below

# 3. Pick the content profile.
make profiles                       # see what's bundled
# Either use a bundled niche (CONTENT_PROFILE=auto_service) or:
make new-client SLUG=my_client PROFILE=auto_service
# … then edit app/bot/content/my_client/*.yaml and set CONTENT_PROFILE=my_client in .env.
make validate-profile PROFILE=my_client

# 4. Launch.
make prod-up

# 5. Verify.
make prod-logs                      # should show "Bot started" within a few seconds
```

Send `/start` to your bot in Telegram. Send `/admin` from an admin ID.

## Required env vars

The minimum that MUST be set in `.env` for prod:

| Variable             | Example                                                  | Notes                                              |
| -------------------- | -------------------------------------------------------- | -------------------------------------------------- |
| `BOT_TOKEN`          | `1234:ABC…`                                              | From @BotFather                                    |
| `ADMIN_IDS`          | `123456789,987654321`                                    | Comma-separated Telegram user IDs                  |
| `ADMIN_API_TOKEN`    | `<long random string>`                                   | Bearer for `/admin/*` HTTP endpoints               |
| `POSTGRES_PASSWORD`  | `<strong password>`                                      | Prod compose refuses to start without this         |
| `DATABASE_URL`       | `postgresql+asyncpg://postgres:<pass>@postgres:5432/leadbot` | Must match POSTGRES_* values                  |
| `CONTENT_PROFILE`    | `auto_service`                                           | Which YAML profile to load                         |
| `APP_ENV`            | `prod`                                                   | Tells the app it's running in production           |
| `APP_DEBUG`          | `false`                                                  | Disables verbose logs                              |
| `DROP_PENDING_UPDATES` | `true`                                                 | Skip messages queued while the bot was down        |

See `.env.example` for the full list with explanations.

## Backups

PostgreSQL data lives in the named volume `pg_data`. A simple nightly backup:

```bash
# /etc/cron.daily/leadbot-backup
#!/bin/sh
set -e
TS=$(date +%Y%m%d-%H%M)
cd /opt/leadbot
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U postgres leadbot | gzip > /var/backups/leadbot-${TS}.sql.gz
find /var/backups -name 'leadbot-*.sql.gz' -mtime +30 -delete
```

Make executable and ensure `/var/backups` exists. Test the restore on a
staging server at least once before relying on it.

## Updates

```bash
cd /opt/leadbot
git pull
make prod-migrate          # run pending alembic upgrades
docker compose -f docker-compose.prod.yml build bot api worker
make prod-up               # rolling restart
```

Update workflow keeps client YAML untouched — only the code rebuilds.

## Webhook mode (optional)

Polling works out of the box and is the recommended default. If you must use
webhook mode (e.g. high update volume or shared hosting):

1. Set `BOT_MODE=webhook` in `.env`.
2. Set `BOT_WEBHOOK_URL=https://yourdomain.com/webhook/telegram`.
3. Set `BOT_WEBHOOK_SECRET=<random>`.
4. Configure nginx / Caddy to proxy `/webhook/telegram` → `127.0.0.1:8000`.
5. Restart: `make prod-up`.

The FastAPI app already exposes the webhook endpoint and validates the secret.

## TLS / reverse proxy (Caddy snippet)

```caddy
yourdomain.com {
    encode gzip
    reverse_proxy /webhook/telegram 127.0.0.1:8000
    reverse_proxy /admin/* 127.0.0.1:8000
    # everything else 404
}
```

The Caddyfile auto-provisions Let's Encrypt; no extra TLS work needed.

## Integrations (optional)

The template ships with two outbound integration channels, both disabled by
default. Enable them per client by setting env vars — no code changes needed.

### Outbound webhooks (CRM, Zapier, Make.com, n8n)

Fires a signed JSON POST on every lead event. The receiver gets:

```json
{
  "event": "lead.created",
  "occurred_at": "2026-05-19T10:00:00+00:00",
  "data": {
    "id": 42, "public_id": "TG-000042", "status": "new", "priority": "normal",
    "title": "...", "description": "...",
    "contact_name": "...", "contact_phone": "...", "contact_username": "...",
    "category": {"id": 1, "slug": "...", "title": "..."},
    "user": {"telegram_id": 100, "username": "...", "first_name": "..."},
    "answers": [{"key": "...", "question_text": "...", "value_text": "..."}],
    "created_at": "...", "closed_at": null, "close_reason": null
  }
}
```

Events: `lead.created`, `lead.status_changed`, `lead.deleted`.

Headers:
- `X-Webhook-Event: lead.created`
- `X-Webhook-Signature: sha256=<hex>` — present when `WEBHOOK_SECRET` is set.
  Receiver should compute HMAC-SHA256 of the raw body with the same secret
  and reject mismatches.

Env:

```env
WEBHOOK_URLS=https://your-crm.example/leadbot,https://hooks.zapier.com/...
WEBHOOK_SECRET=<long random — generate with `openssl rand -hex 32`>
WEBHOOK_TIMEOUT_SECONDS=10
WEBHOOK_MAX_RETRIES=3
```

Retries: 4xx terminates immediately; 5xx / network errors retry with
exponential backoff (0.5s, 1s, 2s, ...) capped at `WEBHOOK_MAX_RETRIES`
attempts. Failures are logged, never raised back into the bot.

### Email notifications

Sends a plain-text email to admin recipients on every new lead. Disabled
when `SMTP_HOST` is empty.

```env
SMTP_HOST=smtp.gmail.com         # or yandex/mail.ru/SendGrid/Mailgun
SMTP_PORT=587
SMTP_USER=bot@yourdomain.com
SMTP_PASSWORD=<app password>
SMTP_FROM=bot@yourdomain.com
SMTP_STARTTLS=true
SMTP_ADMIN_EMAILS=manager@yourdomain.com,owner@yourdomain.com
```

For Gmail, generate an [App Password](https://support.google.com/accounts/answer/185833)
— don't use your account password directly.

SMTP failures are logged and swallowed (a downed SMTP server can't kill
lead creation).

## Monitoring

- **Sentry**: set `SENTRY_DSN` in `.env`. Errors surface in your Sentry project.
- **Healthchecks**: API exposes `GET /healthz` (returns 200 OK on success).
  Wire it to UptimeRobot / Better Uptime for an SMS alert.
- **Logs**: `make prod-logs` for the bot, `docker compose -f
  docker-compose.prod.yml logs api` for the API.

## Troubleshooting

| Problem                                  | Check                                                          |
| ---------------------------------------- | -------------------------------------------------------------- |
| Bot doesn't respond                      | `make prod-logs` — usually wrong `BOT_TOKEN` or webhook + polling clash |
| Old leads disappeared after deploy       | You ran `seed` against a wrong profile — DB still has the data, switch `CONTENT_PROFILE` back |
| Admin can't see `/admin`                 | Their Telegram ID isn't in `ADMIN_IDS` (comma-separated, no spaces) |
| `make prod-up` fails: missing `POSTGRES_PASSWORD` | Set it in `.env` — prod compose refuses to start without it     |
| Migration fails with `StringDataRightTruncationError` | Alembic revision id is too long for `alembic_version.version_num VARCHAR(32)` — keep IDs short |

## Scaling considerations

This template targets **one bot per client**, not multi-tenant. If you need
to host many clients from one process, fork and:

- Add a `tenant_id` column to every table.
- Route by bot token in middleware.
- Load multiple content profiles in memory and dispatch by token.

This is a substantial rewrite — for most resellers, a separate VPS per client
is cheaper and operationally simpler.
