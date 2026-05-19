# Customizing the bot for a new client

The bot is designed so that **the entire client-facing experience lives in
five YAML files** under `app/bot/content/<profile>/`. Switching the niche
means editing YAML, running `make seed`, and restarting. No Python.

This guide walks you through every YAML field, every question type, the
common mistakes, and how to deliver a polished client deploy in under an hour.

## 1. Create the profile

```bash
make new-client SLUG=acme PROFILE=auto_service   # or default / beauty_salon / medical_clinic
```

This copies `app/bot/content/<source>/` to `app/bot/content/acme/` and runs
a validation check immediately. If it doesn't load cleanly, the command exits
non-zero and tells you why.

> **Tip.** Pick the source profile closest to the client's niche — you'll
> have fewer questions to rewrite.

## 2. Edit the five YAML files

### `brand.yaml` — identity

```yaml
company_name: "АвтоСервис «Гараж 24»"        # shown in admin panel header
manager_username: "@garage24_manager"          # for the Support screen
manager_phone: "+7 (812) 555-12-34"
working_hours: "Ежедневно 08:00–22:00"
welcome_intro: "Оставьте заявку — подберём время…"   # first sentence of main menu
support_intro: "Опишите проблему — мастер ответит за 15 минут."
eta_response_hours: 1                          # used in FAQ helpers / future SLA logic
```

### `texts.yaml` — labels and copy

```yaml
main_menu:
  title: "🔧 Гараж 24 — выберите действие."   # title shown above the menu buttons

support:
  intro: "Опишите ситуацию — мастер свяжется в течение 15 минут."

faq:
  intro: "Частые вопросы об автосервисе."

statuses:
  new:         { label: "Новая",        emoji: "🆕" }
  contacted:   { label: "Связались",    emoji: "📞" }
  in_progress: { label: "В работе",     emoji: "🛠" }
  waiting:     { label: "Ждём клиента", emoji: "⏳" }
  done:        { label: "Готово",       emoji: "✅" }
  rejected:    { label: "Отклонена",    emoji: "❌" }
  cancelled:   { label: "Отменена",     emoji: "🚫" }
  deleted:     { label: "Удалена",      emoji: "🗑" }

priorities:
  low:    { label: "Низкий",  emoji: "🔵" }
  normal: { label: "Обычный", emoji: "⚪" }
  high:   { label: "Высокий", emoji: "🟠" }
  urgent: { label: "Срочно",  emoji: "🔴" }

close_reasons:
  rejected:   ["Спам", "Не наш профиль", "Своя причина"]
  done:       ["Работа выполнена", "Своя причина"]
  cancelled:  ["Передумал", "Своя причина"]
```

**Rules:**
- All 8 statuses MUST be present (`new`, `contacted`, `in_progress`, `waiting`,
  `done`, `rejected`, `cancelled`, `deleted`). The bundled tests enforce this.
- Status labels are what the client sees in "Мои заявки". Rephrase to fit the
  domain (e.g. salon: "Подтверждаем" / "Записан" / "Услуга оказана").
- Each `close_reasons` list MUST end with a **"custom" entry** — the last
  string in the list, whatever it's called, opens a free-text prompt. Rename
  it freely for the niche ("Своя причина" → "Другая причина" → "Other reason");
  the bot detects it by **position (last)**, not by label, so localisation
  works out of the box.

### `faq.yaml` — FAQ entries

```yaml
- q: "Нужно ли записываться заранее?"
  a: "Не обязательно, но с записью мы гарантируем место…"

- q: "Даёте ли гарантию?"
  a: "Да: 6 месяцев на работы…"
```

Aim for 5-8 entries that cover the most common pre-sales questions. Each
shows up as a button in the FAQ screen.

### `categories.yaml` — services and their forms

```yaml
- slug: maintenance                   # lowercase + underscores, stable forever
  title: "🔧 ТО / Замена расходников" # what the client sees on the category button
  description: "Плановое ТО, масло, фильтры, тормозные колодки"
  questions:
    - key: car_model                  # snake_case
      text: "Марка, модель и год выпуска?"
      type: text                      # one of: text, long_text, phone, email, number, choice, date, time
      required: true                  # show ↪ Пропустить button if false
    - key: service_kind
      text: "Что нужно сделать?"
      type: choice
      required: true
      options:                        # CHOICE / MULTI_CHOICE need a non-empty options list
        - "Полное ТО"
        - "Замена масла"
        - "Не уверен — посоветуйте"
    - key: preferred_date
      text: "Удобная дата (ДД.ММ.ГГГГ)?"
      type: date                      # bot validates date format
      required: false

# Every profile needs a 'support' category — used by the Support screen.
- slug: support
  title: "Связь с менеджером"
  description: "Обращение в поддержку"
  internal: true                      # hidden from the user-facing category picker
  questions:
    - key: message
      text: "Опишите ваш вопрос"
      type: long_text
      required: true
```

#### Question types

| Type         | Behavior                                                              |
| ------------ | --------------------------------------------------------------------- |
| `text`       | One-line text answer                                                  |
| `long_text`  | Free-form text (no length limit beyond Telegram's)                    |
| `phone`      | Validates Russian / international format                              |
| `email`      | RFC-5322-ish validation                                               |
| `number`     | Digits only                                                           |
| `date`       | `ДД.ММ.ГГГГ` format, validated                                        |
| `time`       | `ЧЧ:ММ` format, validated                                             |
| `choice`     | Renders one button per option, exclusive pick                         |
| `multi_choice` | (Reserved — not yet wired in UI; do not use)                        |
| `file`/`photo` | (Reserved — file upload is a separate wizard step, not a question)  |

#### Rules

- `slug` is the stable identifier — never change it after first deploy
  (existing leads reference it).
- `slug` and `key` must match `^[a-z][a-z0-9_]*$`.
- Question `key`s must be unique within a category.
- `internal: true` hides the category from the user's category picker. Use this
  for the mandatory `support` category and for internal-only flows.

### `config.yaml` — limits and pagination

```yaml
limits:
  max_leads_per_10_minutes: 3   # anti-spam: leads from one user
  max_files_per_lead: 5         # max attachments
  max_file_size_mb: 20

ui:
  page_size_my_leads: 5         # "Мои заявки" pagination
  page_size_admin: 8            # admin lead list pagination
```

Stricter limits for niches that should not have spam (medical clinic),
looser for niches with many photos (autoservice bodywork: 8 files, 25 MB).

## 3. Validate

```bash
make validate-profile PROFILE=acme
```

If the YAML has a typo, missing field, duplicate key, or schema violation,
this command prints the exact error.

## 4. Seed the database

```bash
make seed
```

`app.seed` reads the active `CONTENT_PROFILE` and creates the categories
and form questions in PostgreSQL. **Idempotent**: re-running it updates
question text (matched by `slug` + `key`) but never deletes existing leads.

> If you delete or rename a category slug after the bot is in production,
> existing leads will keep their `category_id` linkage but the slug becomes
> stale. Prefer adding new categories and marking old ones `internal: true`
> to hide them from new submissions.

## 5. Activate

```bash
echo 'CONTENT_PROFILE=acme' >> .env
make dev-up    # or prod-up
```

## Common pitfalls

| Symptom                                              | Cause                                                        |
| ---------------------------------------------------- | ------------------------------------------------------------ |
| Bot crashes on startup with `KeyError: 'deleted'`    | Missing status entry in `texts.yaml` — add all 8 LeadStatus  |
| Category not visible to user                         | `internal: true` set, or no active form (re-run `make seed`) |
| `choice` question shows no buttons                   | Missing or empty `options:` list                             |
| Date validation rejects `2026-05-19`                 | Bot expects `ДД.ММ.ГГГГ` (`19.05.2026`) — explain in question text |
| `make new-client` says "already exists"              | Profile dir already there — `rm -rf app/bot/content/<slug>` to redo |

## Branding tips for a polished delivery

- Replace every emoji where the niche has a stronger one (💅 vs 🔧 for salon).
- Update **all** status labels to match the niche's vocabulary
  («Связались» → «Регистратор связался» / «Подтверждаем» / «На примерке»).
- The first line of `main_menu.title` is your branding moment — short,
  emoji + company name + call-to-action.
- `welcome_intro` in `brand.yaml` is the line under the welcome — keep it
  one sentence, focused on what the bot does for the client.
- Tailor `close_reasons` — the dropdown lists in admin should reflect what
  the manager actually closes leads with.

## Where to go next

- Want to ship to prod? See [`DEPLOY.md`](DEPLOY.md).
- Want to understand the moving parts? See [`ARCHITECTURE.md`](ARCHITECTURE.md).
- Want to add custom fields beyond YAML (DB columns, integrations)?
  Touch Python — see ARCHITECTURE for entry points.
