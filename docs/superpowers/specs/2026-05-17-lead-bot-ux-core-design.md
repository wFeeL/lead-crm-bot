# Lead Bot — Этап 1: UX-ядро, ключевые фичи и конфигурируемость

**Дата:** 2026-05-17
**Статус:** Утверждён к реализации
**Скоуп:** UX-ядро (SPA-навигация), ключевые пользовательские фичи, content-layer для шаблонности продукта.

## Контекст

`lead_management_bot` — коммерческий шаблон Telegram-бота, который пользователь переиспользует под разных клиентов (ремонт, репетиторы, веб-студии и т.д.). Базовый MVP уже реализован: модели (Lead/User/Category/Form/Question/Answer/File/Comment/Event), сервисы (LeadService/StatusService/NotificationService/FormService/RateLimit), репозитории, валидация статусных переходов, админский API, базовая FSM-форма заявки, scheduler с дневным отчётом.

Аудит выявил критические UX-проблемы и пробелы:

**Критические UX-проблемы:**
- Залипания в FSM: команды и невалидные сообщения в состояниях `answering_questions`, `entering_contact`, `AdminCommentState.waiting_for_comment` не очищают состояние и оставляют пользователя в «застрявшем» виде.
- Неконсистентная навигация: смесь `edit_text()` и `answer()` — пользователь видит мусор в истории чата.
- Глобальный fallback (`app/bot/routers/user/start.py:39-45`) не очищает FSM.
- Нет универсального «Назад / Главное меню / Отмена» на каждом экране.
- Нет пагинации в «Мои заявки» (превышение лимита Telegram при >10 заявок).
- Дубли: проверка `question_id`, рендер списка заявок, валидация — повторяются по 3 раза.

**Пробелы по фичам:**
- FAQ — заглушка `"FAQ пока минимальный"`.
- «Связаться с менеджером» — заглушка без действия.
- Нет «Повторить последнюю заявку».
- Inline-комментарии админа есть, но без навигационной обвязки.

**Пробелы по менеджменту заявок (выявлены по best practices Zendesk/Freshservice/amoCRM/Битрикс24):**
- Нет статуса «Связались» между `NEW` и `IN_PROGRESS` — менеджер вынужден ставить «В работе» преждевременно или «Ждём клиента» некорректно.
- Нет `close_reason` — невозможно зафиксировать «почему отклонили / завершили»; страдает аналитика.
- Нет приоритета заявки (low/normal/high/urgent) — стандарт любого ticketing.
- Нет переназначения между админами — есть только «назначить себе».

**Архитектурное требование (стратегическое):**
- Проект — **шаблон-заготовка**, должен легко переориентироваться под нового клиента БЕЗ правки логики. Все клиент-специфичные данные (тексты, бренд, категории, FAQ) — в YAML-конфигах.

## Цель этапа

Принести проект к состоянию, в котором:

1. Пользователь Telegram-бота получает SPA-подобный UX: одно «корневое» сообщение, понятная навигация, никаких залипаний, дружелюбные тексты.
2. Реализованы ключевые недостающие фичи: рабочий FAQ, рабочая поддержка, повтор заявки, удобные файлы.
3. Админ получает полноценный интерфейс заявок прямо в боте: пагинация, фильтры по статусу, inline-комментарии, приоритеты, причины закрытия, переназначение — без бегания в API.
4. Модель статусов и приоритетов отражает реальный менеджмент-флоу: есть промежуточный «Связались», есть `close_reason`, есть приоритеты для срочных заявок.
5. Весь клиент-специфичный контент вынесен в YAML-профиль. Адаптация под нового клиента = 1 каталог YAML + переменная окружения.

Этап **не включает** (отложено на дальнейшие этапы): GitHub Actions/CI, миграция на uv, web-админка, S3-файлы, Sentry, мультиязычность, расширенные admin-функции (поиск, теги, шаблоны ответов, reopen после терминального статуса).

## Архитектура UX (Screen Registry)

### Концепция «Экран»

`Screen` — единица UI, представляющая один логический экран бота. Чистая функция `(context) -> Screen` без побочных эффектов на Telegram.

```python
@dataclass(frozen=True)
class Screen:
    screen_id: str            # 'main_menu', 'faq', 'lead_question', ...
    text: str
    keyboard: InlineKeyboardMarkup
    next_state: State | None = None  # FSM-state, в который переходим после render
    reply_keyboard: ReplyKeyboardMarkup | None = None  # для контактов/фото
```

### Корневое сообщение и SPA-edit

На каждого пользователя хранится **один `root_message_id`** в FSM data. Все экраны рендерятся через `bot.edit_message_text(chat_id, root_message_id, screen.text, reply_markup=screen.keyboard)`.

Исключение — экраны, требующие reply-keyboard (контакт-кнопка, отправка фото):
1. На root-сообщении удаляется inline-клава (`edit_message_reply_markup(reply_markup=None)`).
2. Отправляется временный promt с reply-keyboard.
3. После ввода reply-keyboard убирается (`ReplyKeyboardRemove`), promt удаляется, root-сообщение `edit_text` к следующему экрану.

### Файловая структура

```
app/bot/ui/
  __init__.py
  screen.py             # Screen dataclass
  registry.py           # SCREENS: dict[str, Callable[..., Screen]]
  navigation.py         # nav-stack, push/pop, go_home, go_back
  footer.py             # build_nav_footer(stack, extra_buttons=...)
  render.py             # render_screen(bot, chat_id, root_message_id, screen)
  callbacks.py          # NavCallback factory (nav:back, nav:home, nav:cancel)
  middlewares.py        # EscapeMiddleware
```

### Навигационный стек

Хранится в FSM data: `nav_stack: list[str]`. Каждый push добавляет ScreenId. `nav:back` поппит. `nav:home` чистит стек и идёт на `MAIN_MENU`. `nav:cancel` чистит весь FSM (state.clear()) и идёт на `MAIN_MENU`.

### Универсальный коллбэк-роутер

```python
class NavCallback(CallbackData, prefix="nav"):
    action: Literal["back", "home", "cancel"]

@router.callback_query(NavCallback.filter())
async def handle_nav(callback, callback_data: NavCallback, state: FSMContext):
    ...
```

Один хендлер на всё приложение — отрезает 80% дублей.

### Stale callback защита

Перед обработкой любого коллбэка проверяем `callback.message.message_id == data["root_message_id"]`. Не равно — отвечаем alert «Этот экран устарел, нажмите /menu» и перерисовываем root.

## Каталог экранов

### Пользовательские

| ScreenId              | Назначение | Главные кнопки |
|-----------------------|-----------|---------------|
| `MAIN_MENU`           | Стартовый экран после `/start`, всегда вершина стека | Оставить заявку / Мои заявки / Связаться / FAQ |
| `FAQ`                 | Список вопросов | По кнопке на вопрос → FAQ_ANSWER |
| `FAQ_ANSWER`          | Ответ на конкретный вопрос | ⬅ Назад к FAQ / 🏠 Меню |
| `SUPPORT`             | Контакты менеджера + кнопка написать | ✉️ Написать менеджеру / ⬅ Меню |
| `SUPPORT_WRITING`     | Ввод одного сообщения для менеджера | reply: текст; inline: 🚫 Отмена |
| `MY_LEADS`            | Список заявок пользователя, пагинация 5/стр. | По кнопке на заявку → MY_LEAD_DETAIL; ◀ / ▶ / 🏠 |
| `MY_LEAD_DETAIL`      | Карточка заявки | 🔁 Повторить (если не REJECTED/CANCELLED) / 🚫 Отменить (если NEW) / ⬅ К заявкам / 🏠 Меню |
| `LEAD_CATEGORY`       | Выбор категории | По кнопке на категорию → LEAD_QUESTION; ⬅/🏠 |
| `LEAD_QUESTION`       | Один вопрос формы, прогресс `N/M` | Варианты (если choice); ⬅ Назад / ↪ Пропустить / 🚫 Отмена |
| `LEAD_UPLOAD_FILES`   | Загрузка фото/файлов, счётчик `N/max` | Продолжить ➡ / 🗑 Удалить последний / ⬅ Назад / 🚫 Отмена |
| `LEAD_CONTACT_PROMPT` | Запрос контакта | reply: 📞 Отправить телефон + текстовое поле; inline: ⬅/🚫 |
| `LEAD_CONFIRM`        | Резюме перед отправкой | ✅ Отправить / ✏ Изменить ответы / ➕ Добавить файл / 🚫 |
| `LEAD_DONE`           | Успех + номер заявки | 📋 Мои заявки / 🏠 Меню |

### Админские

| ScreenId                  | Назначение |
|---------------------------|-----------|
| `ADMIN_MENU`              | Дашборд: счётчики по статусам, срочные, кнопки фильтров |
| `ADMIN_LEAD_LIST`         | Пагинированный список (фильтр по статусу/приоритету, сортировка по приоритету) |
| `ADMIN_LEAD_DETAIL`       | Карточка + кнопки статусов, приоритета, комментариев, назначения |
| `ADMIN_COMMENT_PROMPT`    | Ввод комментария (internal / reply клиенту) |
| `ADMIN_CLOSE_REASON`      | Выбор причины при `REJECTED` (обязательно) / `DONE` (опционально) |
| `ADMIN_ASSIGN_LIST`       | Список админов для переназначения, пагинация |

## Пользовательский FSM

```python
class LeadFormState(StatesGroup):
    choosing_category = State()
    answering_questions = State()
    uploading_files = State()
    entering_contact = State()
    confirming = State()

class SupportState(StatesGroup):
    writing_message = State()

class AdminFlowState(StatesGroup):
    writing_internal_comment = State()
    writing_client_reply = State()
    writing_close_reason = State()        # для REJECTED (обязательно) и DONE (опционально, при «Своя причина»)

class MyLeadCancelState(StatesGroup):
    writing_cancel_reason = State()       # клиент выбирает или пишет свою причину отмены
```

### Структура FSM data

```python
{
  "root_message_id": int,
  "nav_stack": list[str],

  "draft_lead": {                       # при создании заявки
    "category_id": int,
    "current_question_idx": int,
    "answers": [{"question_id": int, "key": str, "value": Any}],
    "files": [str],                     # telegram_file_id
    "contact": {"name": ..., "phone": ..., "username": ..., "preferred_time": ...},
    "source": str,                      # 'menu' | 'support' | 'repeat'
  },

  "support_draft": str | None,
  "admin_target_lead_id": int | None,
  "admin_target_status": str | None,    # при writing_close_reason: какой статус ставим после ввода причины
  "admin_assign_page": int,

  "my_leads_page": int,                 # для пагинации
  "my_lead_cancel_target_id": int | None,
  "admin_filter": {"status": str | None, "priority": str | None, "page": int},
}
```

### Защита от залипаний — три уровня

1. **EscapeMiddleware** (на Dispatcher). Перехватывает `/start`, `/menu`, `/cancel` ДО роутеров. Если FSM активна — `state.clear()`, рендер `MAIN_MENU` в root_message_id (или новый, если root утерян).
2. **Per-state fallback handlers**. Каждый State имеет общий `@router.message(StateGroup.X)` fallback: alert «Я жду от вас N — отправьте N или нажмите Отмена». State не чистится.
3. **Stale callback guard** на NavCallback и контекстных коллбэках.

### Транзиции

```
MAIN_MENU                  ─[Оставить заявку]→  choosing_category
choosing_category          ─[категория]→        answering_questions
answering_questions        ─[ответ N/M]→        answering_questions | uploading_files
uploading_files            ─[Продолжить]→       entering_contact
entering_contact           ─[контакт]→          confirming
confirming                 ─[✅]→               save_lead → LEAD_DONE → clear()

ЛЮБОЕ → /cancel или 🚫 Отмена / 🏠 Меню → MAIN_MENU, clear()
ЛЮБОЕ → ⬅ Назад → pop(nav_stack) → previous screen
```

## Статусы, приоритеты и менеджмент

Раздел адаптирует существующую модель статусов под best practices ticketing/lead-management (Zendesk, Freshservice, amoCRM, Битрикс24): 5–7 action-oriented статусов, причина закрытия как отдельное поле, приоритет, переназначение.

### Статусы заявки

Расширяем существующий enum `LeadStatus` (`app/core/constants.py`) одним новым статусом и нормализуем лейблы.

| Код           | Лейбл              | Эмодзи | Назначение |
|---------------|--------------------|--------|-----------|
| `new`         | Новая              | 🆕     | Заявка только что создана, никто не работает |
| `contacted`   | Связались          | 📞     | **НОВЫЙ.** Менеджер связался, идёт первичный обмен, работа ещё не начата |
| `in_progress` | В работе           | 🛠     | Активное выполнение (мастер выехал, дизайнер делает, оператор оформляет) |
| `waiting`     | Ждём клиента       | ⏳     | Заблокировано на стороне клиента (ждём фото, оплату, подтверждение) |
| `done`        | Выполнена          | ✅     | Терминальный. Успешно закрыта |
| `rejected`    | Отклонена          | ❌     | Терминальный. Закрыта менеджером (нет потенциала / спам / дубликат) |
| `cancelled`   | Отменена клиентом  | 🚫     | Терминальный. Клиент отменил сам (только из NEW, см. существующую логику) |

### Переходы статусов (новые `ALLOWED_STATUS_TRANSITIONS`)

```
new         → contacted, in_progress, rejected, cancelled
contacted   → in_progress, waiting, done, rejected, cancelled
in_progress → contacted, waiting, done, rejected, cancelled
waiting     → contacted, in_progress, done, rejected, cancelled
done        → ∅ (терминальный, reopen — out of scope этапа 1)
rejected    → ∅
cancelled   → ∅
```

Логика — менеджер может переключаться между активными статусами свободно (отражает реальную работу: связались → ждём → снова связались → в работу), но из терминальных назад нельзя без owner-инициированного reopen.

### Причина закрытия (`close_reason`)

Новое поле `Lead.close_reason: str | None`, заполняется при переходе в терминальный статус:

- `DONE`: **опционально**, краткое резюме («сделано», «передано в работу мастеру», «оформлено»).
- `REJECTED`: **обязательно**. Менеджер обязан указать причину. На UI — отдельный FSM-state `AdminFlowState.writing_close_reason` с reply-вводом + inline `🚫 Отмена`.
- `CANCELLED`: **обязательно**, заполняется клиентом из карточки `MY_LEAD_DETAIL` (на этапе 1 — короткий преднабор причин из YAML + «Своя причина»).

В `texts.yaml` поставляется набор шаблонов причин — клиент шаблона может расширять под нишу:

```yaml
close_reasons:
  rejected:
    - "Спам / тестовая заявка"
    - "Дубликат существующей"
    - "Нет требуемой услуги"
    - "Клиент не отвечает"
    - "Своя причина"
  cancelled:
    - "Передумал"
    - "Решил вопрос сам"
    - "Слишком долго ждать"
    - "Своя причина"
```

При выборе «Своя причина» открывается reply-prompt. Иначе — выбранная опция сразу сохраняется в `close_reason`.

`LeadEvent` для `STATUS_CHANGED` теперь дополнительно сохраняет `close_reason` в `payload_json`.

### Приоритет (`priority`)

Новое поле `Lead.priority: enum(low, normal, high, urgent)` default `normal`. Менеджер выставляет вручную из `ADMIN_LEAD_DETAIL`.

| Код      | Лейбл    | Эмодзи | Когда использовать |
|----------|----------|--------|---------------------|
| `low`    | Низкий   | 🔵     | Не срочно (общий вопрос, далёкая дата) |
| `normal` | Обычный  | ⚪     | Дефолт |
| `high`   | Высокий  | 🟠     | VIP-клиент, дорогая услуга, сжатый дедлайн |
| `urgent` | Срочный  | 🔴     | Прямо сейчас (авария, экстренный ремонт) |

UI:
- В `ADMIN_LEAD_DETAIL` отдельный ряд кнопок `[🔵] [⚪] [🟠] [🔴]` (текущий помечен галкой `[✓ ⚪]`).
- В `ADMIN_LEAD_LIST` каждая строка начинается с эмодзи приоритета.
- В `ADMIN_MENU` счётчик `🔥 Срочных и высоких: N` — заявки `priority in (high, urgent) AND status NOT IN (done, rejected, cancelled)`.
- В сортировке списка `ADMIN_LEAD_LIST` приоритет первичен (urgent → high → normal → low), внутри одинакового приоритета — по `created_at desc`.

### Переназначение между админами

Существующее `assigned_admin_id` + кнопка «Назначить себе» дополняется полноценным переназначением.

- В `ADMIN_LEAD_DETAIL` кнопка `[👤 Назначить...]` (с галкой текущего назначенного, если есть).
- Открывает `ADMIN_ASSIGN_LIST` — список админов, доступных для назначения. Источник: `User`-ы с `role in (ADMIN, MANAGER, OWNER)` и `is_blocked=false`. ADMIN_IDS из env синхронизируются в БД (это уже есть в `UserMiddleware`).
- В списке — `[ Я (если другой назначен)] [Снять назначение] [Иван @ivan] [Петр @petr] ...`. Pagination 5/стр.
- Клик → `LeadService.assign_to_admin(lead_id, admin_id)` (метод уже существует). Логируется `LeadEvent` `ADMIN_ASSIGNED` с `old_value=<prev_admin_id>` / `new_value=<new_admin_id>`.
- Уведомление новому назначенному: «🔔 На вас назначена заявка №{public_id}» (шаблон в `texts.yaml`).

## Ключевые пользовательские фичи

### Повтор заявки

- Кнопка `🔁 Повторить` показывается на `MY_LEAD_DETAIL` для конкретной заявки, если её `status in (NEW, IN_PROGRESS, WAITING, DONE)`. Не показывается для `REJECTED` и `CANCELLED` — повторять отвергнутую/отменённую бессмысленно.
- Клик → `LeadService.build_draft_from_lead(lead_id, user_id)` создаёт draft в FSM из ответов выбранной заявки → сразу `LEAD_CONFIRM`. Юзер может `✅ Отправить` или `✏ Изменить ответы`.
- На сохранении генерируется новый `submission_key` (uuid4) — существующий unique-constraint не блокирует.
- В draft пишется `source="repeat"`, в `Lead.source` сохраняется при создании — для аналитики «повторных» клиентов.
- Сервис проверяет, что `lead.user_id == current_user.id` (нельзя повторить чужую заявку).

### Связаться с менеджером

- Реализуется как **специальная категория** `slug="support"` в `lead_categories` (seed-данные из `categories.yaml`). Форма из одного вопроса `"Опишите ваш вопрос"` (long_text) + контакт.
- Альтернативный «быстрый» вход: на `SUPPORT` экране кнопка `✉️ Написать менеджеру` ведёт прямо в `SupportState.writing_message`. Пользователь шлёт одно сообщение, бот собирает draft с предзаполненной категорией `support` и контактом из `users` (если есть phone/username), без прохождения всей формы.
- При сохранении `source="support"`. Админ получает уведомление с заголовком `🆘 ОБРАЩЕНИЕ В ПОДДЕРЖКУ` (шаблон в `texts.yaml`).
- Все существующие механизмы (статусы, комментарии, история) работают без изменений.

### FAQ

- Данные из YAML `app/bot/content/<profile>/faq.yaml`:
  ```yaml
  - q: "Сколько ждать ответа?"
    a: "В рабочее время — до 30 минут. После 21:00 — на следующий день."
  - q: "Можно ли отменить заявку?"
    a: "Да, пока статус «Новая». Кнопка в карточке заявки."
  ```
- Загружается в `ContentService` при старте.
- Экран `FAQ` рендерит список вопросов как inline-кнопки (id вопроса в callback). `FAQ_ANSWER` показывает ответ + навигацию.

### UX-улучшения файлов

- Счётчик `Загружено: 2/5` в тексте экрана, обновляется при каждом фото/документе.
- Превью списка имён прикреплённых файлов.
- Кнопка `🗑 Удалить последний файл` (поп из FSM `draft_lead.files`).
- Существующие лимиты (`max_files_per_lead`, `max_file_size_bytes`) сохраняются.

### Дружелюбные тексты

- `MAIN_MENU` приветствие с описанием продукта, бренд из `brand.yaml`.
- `LEAD_DONE` объясняет «что дальше»: ожидаемое время ответа, где смотреть статус.
- Ошибки валидации указывают, что именно ожидалось.
- Все тексты — из `texts.yaml`, с эмодзи, с подстановками типа `{user_name}`, `{public_id}`, `{eta_hours}`.

## Админский интерфейс

### ADMIN_MENU

```
🛠 Админ-панель — {company_name}

🆕 Новые: {new_count}
📞 Связались: {contacted_count}
🛠 В работе: {in_progress_count}
⏳ Ждут клиента: {waiting_count}

🔥 Срочных и высоких: {hot_count}

[🆕 Новые] [📞 Связались] [🛠 В работе] [⏳ Ждут]
[🔥 Срочные] [📋 Все заявки] [📤 CSV]
[📊 Статистика дня]
```

Счётчики — новые методы `LeadRepository.status_counts()` (общее количество в статусе, не дневная статистика) и `LeadRepository.hot_count()` (приоритет high+urgent в нетерминальных). Существующий `daily_status_counts()` оставляем для `📊 Статистика дня`.

### ADMIN_LEAD_LIST

- Пагинация по 5, аналогично `MY_LEADS`.
- Параметризуется фильтром (`status=None|new|contacted|in_progress|waiting|done|rejected|cancelled`, `priority=None|low|normal|high|urgent`, плюс спец-фильтр `hot=true` для high+urgent).
- Сортировка: `priority desc, created_at desc` (urgent сверху).
- Каждая строка: `{priority_emoji} №{public_id} · {status_emoji} · {age} · {category_short}`.
- Футер: `[◀ p/N ▶] [⬅ Админ-меню] [🏠 Меню]`.

### ADMIN_LEAD_DETAIL

```
Заявка №{public_id} · {status_emoji} {status_label} · {priority_emoji} {priority_label}
Клиент: {name} {username_link}
Категория: {category_title}
Назначен: {assigned_admin_or_dash}
Создана: {created_relative}

{lead_summary}

[📞 Связались] [🛠 В работу] [⏳ Ждать клиента]
[✅ Завершить] [❌ Отклонить]
[ {priority_low_btn} {priority_normal_btn} {priority_high_btn} {priority_urgent_btn} ]
[📝 Внутренний] [💬 Клиенту] [👤 Назначить...]
[⬅ К списку] [🏠 Меню]
```

- Кнопки статусов формируются динамически из `available_statuses(current_status)` (см. `ALLOWED_STATUS_TRANSITIONS`).
- Кнопки приоритета — всегда 4, текущий помечен галкой `✓`.
- Stale callback guard защищает от двойного нажатия.
- `[👤 Назначить...]` ведёт в `ADMIN_ASSIGN_LIST`.

### ADMIN_COMMENT_PROMPT

- Отдельный State в `AdminFlowState`: `writing_internal_comment` или `writing_client_reply` (разделили вместо `is_internal=bool`).
- Reply-keyboard убран; ввод через обычный текст.
- Inline-кнопка `🚫 Отменить комментарий` всегда видна.
- После сохранения возврат в `ADMIN_LEAD_DETAIL`.

### ADMIN_CLOSE_REASON

- Показывается при переходе в `REJECTED` (обязательно) или при выборе «Своя причина» для `DONE` (опционально).
- Текст: «Укажите причину отказа» / «Краткое резюме (можно пропустить)».
- Кнопки: список преднаборных причин из `texts.yaml` `close_reasons.rejected` / `close_reasons.done`, плюс `✍ Своя причина` (открывает FSM `writing_close_reason` reply-вводом) и `🚫 Отмена`.
- После сохранения `Lead.close_reason` обновляется, `LeadService.change_status()` вызывается с этой причиной в `payload_json` события, возврат в `ADMIN_LEAD_DETAIL`.

### ADMIN_ASSIGN_LIST

- Текст: «Кому назначить заявку №{public_id}?»
- Кнопки в столбик: `[👤 Я (если другой)] [➖ Снять назначение] [Иван @ivan] [Пётр @petr] ...`.
- Пагинация 5/стр.
- Footer: `[◀ p/N ▶] [⬅ К заявке] [🏠 Меню]`.
- Источник: `UserRepository.list_admins()` — пользователи с `role in (ADMIN, MANAGER, OWNER) AND NOT is_blocked`.

### MY_LEAD_DETAIL — отмена клиентом

Клиентская кнопка `🚫 Отменить заявку` теперь ведёт не сразу в `cancel_by_client`, а на промежуточный экран выбора причины (`MyLeadCancelState.writing_cancel_reason`). Преднабор причин — `texts.yaml` `close_reasons.cancelled` + «Своя причина». Это симметрично админскому `REJECTED` и даёт менеджеру понимание, почему клиенты отказываются.

## Конфигурируемость (Content Layer)

### Файловая структура контента

```
app/bot/content/
  default/                 # дефолтный профиль, поставляется в шаблоне
    brand.yaml
    texts.yaml
    faq.yaml
    categories.yaml
    config.yaml
  examples/                # готовые профили под ниши
    web_studio/
    tutor/
    repair/
    auto_service/
```

### `brand.yaml`

```yaml
company_name: "LeadBot Demo"
manager_username: "@manager_demo"
manager_phone: "+7 (000) 000-00-00"
working_hours: "Пн-Пт 09:00–21:00"
welcome_intro: "Здесь вы можете оставить заявку — мы свяжемся в течение рабочего дня."
support_intro: "Опишите ваш вопрос — менеджер ответит лично."
eta_response_hours: 24
```

### `texts.yaml`

```yaml
main_menu:
  title: "👋 {company_name}\n\n{welcome_intro}"
  buttons:
    create_lead: "📝 Оставить заявку"
    my_leads: "📋 Мои заявки ({count})"
    support: "💬 Связаться с менеджером"
    faq: "❓ FAQ"

my_lead_detail:
  buttons:
    repeat: "🔁 Повторить"
    cancel: "🚫 Отменить заявку"
    back: "⬅ К заявкам"

lead_done:
  title: "✅ Заявка №{public_id} принята!"
  body: "Менеджер свяжется в течение {eta_response_hours} часов.\nСтатус можно отслеживать в «Мои заявки»."

errors:
  invalid_phone: "Похоже, это не телефон. Пример: +7 999 111-22-33"
  invalid_email: "Похоже, это не email. Пример: name@example.com"
  state_fallback: "Я жду от вас {expected}. Отправьте {expected} или нажмите 🚫 Отмена."

notifications:
  admin_new_lead: "🆕 Заявка №{public_id}\nКлиент: {client_name} {client_username}\n..."
  admin_support: "🆘 ОБРАЩЕНИЕ В ПОДДЕРЖКУ\nКлиент: ..."
  admin_assigned: "🔔 На вас назначена заявка №{public_id}"
  client_status_changed: "Статус заявки №{public_id}: {status_label}"

statuses:
  new:         { label: "Новая",            emoji: "🆕" }
  contacted:   { label: "Связались",        emoji: "📞" }
  in_progress: { label: "В работе",         emoji: "🛠" }
  waiting:     { label: "Ждём клиента",     emoji: "⏳" }
  done:        { label: "Выполнена",        emoji: "✅" }
  rejected:    { label: "Отклонена",        emoji: "❌" }
  cancelled:   { label: "Отменена",         emoji: "🚫" }

priorities:
  low:     { label: "Низкий",   emoji: "🔵" }
  normal:  { label: "Обычный",  emoji: "⚪" }
  high:    { label: "Высокий",  emoji: "🟠" }
  urgent:  { label: "Срочный",  emoji: "🔴" }

close_reasons:
  rejected:
    - "Спам / тестовая заявка"
    - "Дубликат существующей"
    - "Нет требуемой услуги"
    - "Клиент не отвечает"
    - "Своя причина"
  done:
    - "Выполнено"
    - "Передано мастеру"
    - "Своя причина"
  cancelled:
    - "Передумал"
    - "Решил вопрос сам"
    - "Слишком долго ждать"
    - "Своя причина"
```

### `faq.yaml`

```yaml
- q: "Сколько ждать ответа?"
  a: "..."
```

### `categories.yaml`

(перенос текущего хардкода из `app/services/forms.py:92`)

```yaml
- slug: telegram_bot
  title: "Разработка Telegram-бота"
  description: "..."
  questions:
    - key: goal
      text: "Что должен делать бот?"
      type: long_text
      required: true
    - key: deadline
      text: "Какие сроки?"
      type: text
      required: false

- slug: support
  title: "Связь с менеджером"
  internal: true              # не показывается в LEAD_CATEGORY, используется поддержкой
  questions:
    - key: message
      text: "Опишите ваш вопрос"
      type: long_text
      required: true
```

### `config.yaml`

```yaml
limits:
  max_leads_per_10_minutes: 3
  max_files_per_lead: 5
  max_file_size_mb: 20
ui:
  page_size_my_leads: 5
  page_size_admin: 5
```

> Лимиты дублируются с `Settings` сознательно: env остаётся источником правды для деплоя (можно переопределить per-environment), а YAML — для дефолтов профиля клиента. При загрузке `Settings` берёт верх; YAML используется только если env не задан.

### `ContentService`

```
app/services/content.py
  ContentService.load(profile_dir) -> ContentBundle
  ContentBundle:
    brand: BrandConfig (pydantic)
    texts: TextsConfig (вложенный dict с автоподстановкой)
    faq: list[FaqEntry]
    categories: list[CategoryConfig]
    config: AppConfig
  ContentService.text(key, **kwargs) -> str  # с format()
```

- Pydantic-схемы — в `app/schemas/content.py`. Невалидный YAML = бот не стартует (fail fast).
- При старте `ContentService` синглтон в `app.state` (FastAPI) и в `dispatcher["content"]` (aiogram).
- Профиль выбирается через `CONTENT_PROFILE=<name>` в `.env`, дефолт — `default`.
- `python -m app.seed` запускает `ensure_seed_data(content)` — upsert категорий и вопросов по `slug`/`key`.

### Документация шаблона

В `README.md` появляется раздел «Как адаптировать шаблон под нового клиента»:

1. `cp -r app/bot/content/default app/bot/content/<client_name>`
2. Отредактировать YAML (brand, texts, categories, faq, config).
3. `CONTENT_PROFILE=<client_name>` в `.env`.
4. `python -m app.seed` — категории и вопросы зальются в БД.
5. Запуск.

## Рефакторинг существующего кода

- `app/bot/keyboards/builders.py` — выделить `nav_footer(stack, extra=...)`, убрать дубли `FlowCallback` (разнести по contextual callbacks: `LeadFlowCallback`, `MyLeadsCallback`).
- `app/bot/routers/user/lead_create.py` — декоратор `@validate_question_context` для проверки `callback_data.question_id == current_question`. Применить к `skip_optional_question`, `collect_choice_answer`, `back_to_previous_question`.
- `app/bot/routers/user/my_leads.py` — выделить `render_my_leads_screen(state, page)`, переиспользовать в `my_leads()` и `back_to_my_leads()`.
- `app/bot/texts/user.py` удаляется. Все строки через `content.text(...)`.
- `app/bot/middlewares/db.py` — логирование исключений с `lead_id`/`user_id` в контексте.
- `app/services/formatting.py` — `selectinload(LeadComment.admin)` в `_lead_options()` чтобы убрать N+1 на админе комментария.
- `app/services/forms.py:92` (`ensure_seed_data`) — переписать на загрузку из `ContentService.categories`.

## Миграции БД

Конфиг-фичи не требуют миграций (FAQ, тексты, бренд — YAML). Для управления статусами и приоритетами добавляются три миграции по порядку зависимостей:

### `0003_add_category_is_internal.py`

- Поле `lead_categories.is_internal: bool` (default `false`).
- `support`-категория помечается `is_internal=true` (seed).
- Применяется до Шага 3 (фильтрация в `LEAD_CATEGORY`).

### `0004_add_contacted_status_and_close_reason_priority.py`

Основная миграция этапа. Объединена в одну, чтобы статусные изменения катились атомарно:

- Добавляется значение `'contacted'` в enum `lead_status` (PostgreSQL `ALTER TYPE ... ADD VALUE`). Если БД-движок — SQLite (тесты) — миграция использует тип `VARCHAR` с `CHECK`-констрейнтом, добавление значения = пересоздание констрейнта.
- Добавляется столбец `leads.close_reason: VARCHAR(500) NULL`.
- Добавляется enum-тип `lead_priority` (`low`, `normal`, `high`, `urgent`) и столбец `leads.priority: lead_priority NOT NULL DEFAULT 'normal'`.
- Backfill: всем существующим заявкам ставится `priority='normal'` (через default — автоматически).
- Применяется до Шага 5 (admin UI зависит от полей).

### `0005_indexes_and_cascades.py`

Финальная sanity-миграция:

- Индексы: `leads(assigned_admin_id)`, `leads(priority, created_at DESC)`, `leads(status, created_at DESC)`, `lead_comments(lead_id)`, `lead_files(lead_id)`, `lead_events(lead_id, created_at)`.
- `ondelete`-правила на FK:
  - `lead_comments.admin_id` → `ON DELETE SET NULL`
  - `leads.assigned_admin_id` → `ON DELETE SET NULL`

### Обновления в моделях SQLAlchemy

- `app/db/models/lead.py`: `close_reason: Mapped[str | None]`, `priority: Mapped[LeadPriority]`.
- `app/core/constants.py`: добавить `LeadStatus.CONTACTED`, `LeadPriority` enum, обновить `ALLOWED_STATUS_TRANSITIONS`.
- `app/schemas/lead.py`: добавить поля в admin-схемы.

## План имплементации (черновик для writing-plans)

Каждый шаг — отдельная коммит-история, TDD, зелёные тесты + ruff перед следующим.

### Шаг 0. Content layer

- `app/schemas/content.py` — Pydantic-схемы `BrandConfig`, `TextsConfig`, `FaqEntry`, `CategoryConfig`, `QuestionConfig`, `AppConfig`.
- `app/services/content.py` — `ContentService.load(profile_dir)`, `text(key, **kwargs)`.
- `app/bot/content/default/*` — YAML с текущим содержанием бота (миграция текстов из `app/bot/texts/user.py` и категорий из `app/services/forms.py`).
- `CONTENT_PROFILE` env-переменная.
- `Settings.content_profile`.
- Интеграция: `app/main.py` и `app/bot_main.py` загружают content в startup.
- `python -m app.seed` берёт категории из content.
- Тесты: загрузка дефолтного профиля, валидация невалидного YAML, подстановки в `text(...)`.

### Шаг 1. Фундамент SPA-навигации

- `app/bot/ui/screen.py`, `registry.py`, `navigation.py`, `footer.py`, `render.py`, `callbacks.py`.
- `NavCallback` + универсальный handler.
- `EscapeMiddleware`.
- `root_message_id` в FSM.
- Stale callback guard как утилита.
- Тесты: рендер MAIN_MENU, nav-stack push/pop, escape-middleware на FSM-state.

### Шаг 2. Миграция простых экранов

- MAIN_MENU (с динамическим счётчиком заявок).
- MY_LEADS с пагинацией.
- MY_LEAD_DETAIL (с кнопкой `🔁 Повторить` для не-терминальных статусов и `🚫 Отменить` для NEW).
- SUPPORT (контакты из brand.yaml) + SUPPORT_WRITING (FSM).
- FAQ + FAQ_ANSWER.
- Удалить `START_TEXT`, `FAQ_TEXT`, `SUPPORT_TEXT` из `app/bot/texts/user.py`.

### Шаг 3. FSM формы заявки на Screen

- LEAD_CATEGORY (без internal-категорий).
- LEAD_QUESTION (с прогрессом, ⬅/↪/🚫).
- LEAD_UPLOAD_FILES с UX-улучшениями (счётчик, удаление).
- LEAD_CONTACT_PROMPT.
- LEAD_CONFIRM.
- LEAD_DONE.
- Per-state fallback handlers.
- Декоратор `@validate_question_context`.
- Тесты: happy path, отмена, назад, fallback.

### Шаг 4. Новые фичи пользователя

- «Повторить заявку» из `MY_LEAD_DETAIL` (`LeadService.build_draft_from_lead(lead_id, user_id)`, owner-check).
- «Связаться с менеджером» через support-категорию.
- Все шаблоны уведомлений через `content.text(...)`.

### Шаг 5. Админский UI на Screen + менеджмент-фичи

- `LeadStatus.CONTACTED` в constants, обновлённые `ALLOWED_STATUS_TRANSITIONS`.
- `LeadPriority` enum + расширение `LeadService` (`set_priority`, `reassign`, `change_status(close_reason=...)`).
- `LeadRepository.status_counts()`, `hot_count()`, фильтр по `priority`, сортировка `priority desc, created_at desc`.
- `UserRepository.list_admins()` — для назначения.
- ADMIN_MENU со счётчиками всех 4-х активных статусов + срочные.
- ADMIN_LEAD_LIST с пагинацией, фильтром по статусу/приоритету, эмодзи приоритета в каждой строке.
- ADMIN_LEAD_DETAIL: новые кнопки `📞 Связались`, ряд приоритета, `👤 Назначить...`, изменённый отказ с обязательным `close_reason`.
- ADMIN_COMMENT_PROMPT (с разделением internal/reply на разные State).
- ADMIN_CLOSE_REASON (новый экран, FSM `writing_close_reason`).
- ADMIN_ASSIGN_LIST (новый экран, callback-driven, без FSM).
- Уведомление `admin_assigned` назначенному админу.
- Stale callback guard на статусные кнопки.
- Тесты: транзиции с `CONTACTED`, обязательность `close_reason` при `REJECTED`, сортировка по приоритету, переназначение с логированием события.

### Шаг 6. Рефакторинг

- Хелперы из дублей.
- `selectinload(comments.admin)`.
- Удалить `app/bot/texts/user.py`.

### Шаг 7. Миграции БД

Три миграции по порядку зависимостей (см. секцию «Миграции БД»):

- `0003_add_category_is_internal.py` — до Шага 3.
- `0004_add_contacted_status_and_close_reason_priority.py` — до Шага 5.
- `0005_indexes_and_cascades.py` — финальная.

Фактический порядок в writing-plans: Шаг 0 → 0003-миграция → Шаги 1–4 → 0004-миграция → Шаг 5 → Шаг 6 → 0005-миграция → Шаг 8.

### Шаг 8. Тесты бота

- Новый каталог `tests/bot/`.
- FSM-флоу заявки (happy path + отмена + назад + fallback).
- Pagination My Leads / Admin.
- Support flow.
- Content layer integration.
- Менеджмент-флоу: смена статуса через `CONTACTED`, обязательный `close_reason` при `REJECTED`, выбор приоритета, переназначение с уведомлением.
- Клиентская отмена с причиной из преднабора и «Своя причина».

## Out of scope (этап 2+)

- GitHub Actions / pre-commit.
- Миграция на uv.
- Sentry интеграция.
- Web-админка.
- S3 для файлов.
- Расширенные admin-функции (поиск, теги, шаблоны ответов, reopen после терминального статуса).
- Мультиязычность.
- Excel-экспорт.
- Webhook-интеграции с CRM (amoCRM, Bitrix24).
- Non-root user в Dockerfile.
- Готовые examples-профили под ниши — каркас создаём в этапе 1 (пустые каталоги), наполнение в этапе 2.

## Критерии готовности этапа

1. Пользователь ни в одном сценарии не «залипает» в FSM — есть способ выйти на главное меню из любого состояния.
2. Каждый экран имеет навигационный футер (соответствующий контексту).
3. Создание заявки происходит в одном root-сообщении (за исключением reply-промптов для контакта/фото).
4. «Мои заявки» с пагинацией работает на 50+ заявок.
5. «Повторить заявку», «Связаться с менеджером», FAQ — рабочие, не заглушки.
6. Админ может вести всю работу с заявкой через кнопки в боте: смена статуса (включая `CONTACTED`), приоритет, переназначение, комментарии (internal/reply), обязательная причина при отказе.
7. В `ADMIN_LEAD_LIST` сортировка по приоритету работает, в `ADMIN_MENU` счётчики корректны (4 активных статуса + срочные).
8. Клиент при отмене заявки выбирает причину; админ при отказе обязан её указать. Причины храняться в `Lead.close_reason`, фиксируются в `LeadEvent.payload_json`.
9. Адаптация под нового клиента: копирование `default/` → правка YAML → `seed` → запуск. Без правок кода. В частности — статусные лейблы, приоритеты и преднабор причин — конфигурируемы через `texts.yaml`.
10. `pytest` зелёный, новые тесты для bot/ покрывают основные FSM-флоу и менеджмент-флоу.
11. `ruff check .` зелёный.
