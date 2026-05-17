# Step 5 — Admin UI + Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Переписать админский интерфейс на Screen-инфраструктуру с поддержкой CONTACTED статуса, приоритетов, переназначения, обязательной причины при отказе.

**Architecture:** 6 admin-экранов (ADMIN_MENU, ADMIN_LEAD_LIST, ADMIN_LEAD_DETAIL, ADMIN_COMMENT_PROMPT, ADMIN_CLOSE_REASON, ADMIN_ASSIGN_LIST). Существующие `/admin`, `/new`, `/leads`, `/export` команды → entry points в screen-flow. Старый `admin_lead_keyboard()` остаётся для notification (используется в `notify_new_lead`) до Step 6.

**Spec sections:** «Админский интерфейс», «Статусы и приоритеты», «Переназначение между админами», «ADMIN_CLOSE_REASON».

---

## File Structure

**Create:**
- `app/bot/screens/admin_menu.py`
- `app/bot/screens/admin_lead_list.py`
- `app/bot/screens/admin_lead_detail.py`
- `app/bot/screens/admin_comment_prompt.py`
- `app/bot/screens/admin_close_reason.py`
- `app/bot/screens/admin_assign_list.py`
- `app/bot/states/admin_flow.py` (replaces single-state AdminCommentState)
- `app/bot/routers/admin/menu.py` — NEW admin entry
- Tests in `tests/unit/test_screens_admin_*.py` + `tests/integration/test_admin_flow.py`

**Modify:**
- `app/db/repositories/leads.py` — new methods `status_counts()`, `hot_count()`, `list_by_filter(status, priority, page, page_size, sort_by_priority)`, `count_by_filter()`
- `app/db/repositories/users.py` — `list_admins()`
- `app/bot/routers/admin/leads.py` — REWRITE (or replace via menu.py + keep legacy commands)
- `app/bot/create.py` — register new admin router
- `app/bot/states/lead.py` — replace `AdminCommentState` with `AdminFlowState` from admin_flow.py
- `app/services/leads.py` — `change_status(reason=...)` requires reason if status==REJECTED

**Untouched:**
- `app/bot/keyboards/builders.py` — admin_lead_keyboard still used by `notify_new_lead`. Step 6 will replace.
- `app/services/notifications.py` — still uses old keyboard for new-lead notification. The notification could optionally include a `Detail` button that opens the new ADMIN_LEAD_DETAIL — left for follow-up.

---

## Task 5.1 — Repository methods

In `app/db/repositories/leads.py`:

```python
    async def status_counts(self) -> dict[str, int]:
        """Total count per status across ALL leads (not date-filtered)."""
        from sqlalchemy import func, select
        result = await self.session.execute(
            select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
        )
        return {row[0]: row[1] for row in result.all()}

    async def hot_count(self) -> int:
        """Count of non-terminal leads with priority high or urgent."""
        from sqlalchemy import func, select
        result = await self.session.execute(
            select(func.count(Lead.id)).where(
                Lead.priority.in_(("high", "urgent")),
                Lead.status.not_in(("done", "rejected", "cancelled")),
            )
        )
        return int(result.scalar_one())

    async def list_by_filter(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        hot: bool = False,
        limit: int = 5,
        offset: int = 0,
    ) -> list[Lead]:
        """List leads sorted by priority DESC then created_at DESC."""
        from sqlalchemy import case, desc, select
        # priority sort: urgent > high > normal > low. Map to numeric.
        priority_order = case(
            (Lead.priority == "urgent", 4),
            (Lead.priority == "high", 3),
            (Lead.priority == "normal", 2),
            (Lead.priority == "low", 1),
            else_=0,
        )
        stmt = select(Lead).options(*self._lead_options())
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if priority is not None:
            stmt = stmt.where(Lead.priority == priority)
        if hot:
            stmt = stmt.where(
                Lead.priority.in_(("high", "urgent")),
                Lead.status.not_in(("done", "rejected", "cancelled")),
            )
        stmt = stmt.order_by(desc(priority_order), desc(Lead.created_at)).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_filter(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        hot: bool = False,
    ) -> int:
        from sqlalchemy import func, select
        stmt = select(func.count(Lead.id))
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if priority is not None:
            stmt = stmt.where(Lead.priority == priority)
        if hot:
            stmt = stmt.where(
                Lead.priority.in_(("high", "urgent")),
                Lead.status.not_in(("done", "rejected", "cancelled")),
            )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
```

In `app/db/repositories/users.py`:

```python
    async def list_admins(self) -> list[User]:
        """List non-blocked admins / managers / owners."""
        from sqlalchemy import select
        from app.core.constants import UserRole
        result = await self.session.execute(
            select(User).where(
                User.role.in_((UserRole.ADMIN, UserRole.MANAGER, UserRole.OWNER)),
                User.is_blocked.is_(False),
            ).order_by(User.id)
        )
        return list(result.scalars().all())
```

Tests in `tests/integration/test_lead_service.py` (or new file): each method's basic case.

Commit: `feat(db): status_counts, hot_count, list_by_filter, list_admins repository methods`

---

## Task 5.2 — Admin screen renderers (6)

### ADMIN_MENU (`app/bot/screens/admin_menu.py`)

```python
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_MENU_SCREEN_ID = "admin_menu"


class AdminMenuCallback(CallbackData, prefix="adm_menu"):
    action: Literal["new", "contacted", "in_progress", "waiting", "all", "hot", "csv", "stats"]


def render_admin_menu(
    *,
    content: ContentService,
    status_counts: dict[str, int],
    hot_count: int,
    company_name: str,
) -> Screen:
    text = (
        f"🛠 <b>Админ-панель — {company_name}</b>\n\n"
        f"🆕 Новые: {status_counts.get('new', 0)}\n"
        f"📞 Связались: {status_counts.get('contacted', 0)}\n"
        f"🛠 В работе: {status_counts.get('in_progress', 0)}\n"
        f"⏳ Ждут клиента: {status_counts.get('waiting', 0)}\n\n"
        f"🔥 Срочных и высоких: {hot_count}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🆕 Новые", callback_data=AdminMenuCallback(action="new").pack()),
            InlineKeyboardButton(text="📞 Связались", callback_data=AdminMenuCallback(action="contacted").pack()),
        ],
        [
            InlineKeyboardButton(text="🛠 В работе", callback_data=AdminMenuCallback(action="in_progress").pack()),
            InlineKeyboardButton(text="⏳ Ждут", callback_data=AdminMenuCallback(action="waiting").pack()),
        ],
        [
            InlineKeyboardButton(text="🔥 Срочные", callback_data=AdminMenuCallback(action="hot").pack()),
            InlineKeyboardButton(text="📋 Все", callback_data=AdminMenuCallback(action="all").pack()),
        ],
        [
            InlineKeyboardButton(text="📤 CSV", callback_data=AdminMenuCallback(action="csv").pack()),
            InlineKeyboardButton(text="📊 Статистика дня", callback_data=AdminMenuCallback(action="stats").pack()),
        ],
    ])
    return Screen(screen_id=ADMIN_MENU_SCREEN_ID, text=text, keyboard=keyboard)
```

### ADMIN_LEAD_LIST (`app/bot/screens/admin_lead_list.py`)

```python
from collections.abc import Sequence
from math import ceil
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_LEAD_LIST_SCREEN_ID = "admin_lead_list"


class AdminLeadListCallback(CallbackData, prefix="adm_list"):
    action: Literal["page", "open"]
    page: int = 1
    lead_id: int = 0


def render_admin_lead_list(
    *,
    content: ContentService,
    leads: list[Any],
    page: int,
    total: int,
    page_size: int,
    filter_label: str,
    stack: Sequence[str],
) -> Screen:
    total_pages = max(1, ceil(total / page_size))
    if total == 0:
        text = f"📋 {filter_label}\n\nНичего не найдено."
        keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
        return Screen(screen_id=ADMIN_LEAD_LIST_SCREEN_ID, text=text, keyboard=keyboard)

    text = f"📋 <b>{filter_label}</b> (всего {total}):"
    extra = []
    for lead in leads:
        status_emoji = (
            content.texts.statuses[lead.status].emoji
            if lead.status in content.texts.statuses else "•"
        )
        priority_emoji = (
            content.texts.priorities[lead.priority].emoji
            if lead.priority in content.texts.priorities else " "
        )
        category_title = getattr(lead.category, "title", "?") if getattr(lead, "category", None) else "?"
        label = f"{priority_emoji} {status_emoji} №{lead.public_id} · {category_title}"
        extra.append([
            InlineKeyboardButton(
                text=label,
                callback_data=AdminLeadListCallback(action="open", lead_id=lead.id, page=page).pack(),
            )
        ])

    pagination_row = []
    if page > 1:
        pagination_row.append(InlineKeyboardButton(
            text="◀", callback_data=AdminLeadListCallback(action="page", page=page - 1).pack(),
        ))
    pagination_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        pagination_row.append(InlineKeyboardButton(
            text="▶", callback_data=AdminLeadListCallback(action="page", page=page + 1).pack(),
        ))
    extra.append(pagination_row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=ADMIN_LEAD_LIST_SCREEN_ID, text=text, keyboard=keyboard)
```

### ADMIN_LEAD_DETAIL (`app/bot/screens/admin_lead_detail.py`)

```python
from collections.abc import Sequence
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.core.constants import ALLOWED_STATUS_TRANSITIONS, LeadStatus
from app.services.content import ContentService

ADMIN_LEAD_DETAIL_SCREEN_ID = "admin_lead_detail"


class AdminDetailCallback(CallbackData, prefix="adm_det"):
    action: Literal["set_status", "set_priority", "comment_internal", "comment_reply", "assign", "assign_me"]
    lead_id: int
    value: str = ""  # For set_status / set_priority


def render_admin_lead_detail(
    *,
    content: ContentService,
    lead: Any,
    stack: Sequence[str],
) -> Screen:
    status_meta = content.texts.statuses.get(lead.status)
    priority_meta = content.texts.priorities.get(lead.priority)
    category_title = getattr(lead.category, "title", "?") if getattr(lead, "category", None) else "?"
    assigned_text = "—"
    if getattr(lead, "assigned_admin", None):
        admin = lead.assigned_admin
        username = f"@{admin.username}" if admin.username else f"id{admin.id}"
        assigned_text = f"{admin.first_name or ''} {username}".strip()

    lines = [
        f"<b>Заявка №{lead.public_id}</b> · {status_meta.emoji if status_meta else ''} {status_meta.label if status_meta else lead.status} · "
        f"{priority_meta.emoji if priority_meta else ''} {priority_meta.label if priority_meta else lead.priority}",
        f"Категория: {category_title}",
        f"Контакт: {lead.contact_phone or lead.contact_username or '—'}",
        f"Назначен: {assigned_text}",
        f"Создана: {lead.created_at.isoformat(timespec='minutes')}",
        "",
        lead.description or "",
    ]
    if lead.close_reason:
        lines.append(f"\n💬 Причина закрытия: {lead.close_reason}")
    text = "\n".join(lines)

    # Status buttons (dynamic per available transitions)
    available = ALLOWED_STATUS_TRANSITIONS.get(LeadStatus(lead.status), set())
    status_row = []
    for target in (LeadStatus.CONTACTED, LeadStatus.IN_PROGRESS, LeadStatus.WAITING):
        if target in available:
            meta = content.texts.statuses.get(target.value)
            status_row.append(InlineKeyboardButton(
                text=f"{meta.emoji if meta else ''} {meta.label if meta else target.value}",
                callback_data=AdminDetailCallback(
                    action="set_status", lead_id=lead.id, value=target.value
                ).pack(),
            ))
    close_row = []
    for target in (LeadStatus.DONE, LeadStatus.REJECTED):
        if target in available:
            meta = content.texts.statuses.get(target.value)
            close_row.append(InlineKeyboardButton(
                text=f"{meta.emoji if meta else ''} {meta.label if meta else target.value}",
                callback_data=AdminDetailCallback(
                    action="set_status", lead_id=lead.id, value=target.value
                ).pack(),
            ))

    # Priority row (always 4 buttons; current marked).
    prio_row = []
    for p in ("low", "normal", "high", "urgent"):
        meta = content.texts.priorities.get(p)
        mark = "✓ " if lead.priority == p else ""
        prio_row.append(InlineKeyboardButton(
            text=f"{mark}{meta.emoji if meta else ''}",
            callback_data=AdminDetailCallback(
                action="set_priority", lead_id=lead.id, value=p
            ).pack(),
        ))

    # Comments + assignment row.
    actions_row1 = [
        InlineKeyboardButton(
            text="📝 Внутренний",
            callback_data=AdminDetailCallback(
                action="comment_internal", lead_id=lead.id
            ).pack(),
        ),
        InlineKeyboardButton(
            text="💬 Клиенту",
            callback_data=AdminDetailCallback(
                action="comment_reply", lead_id=lead.id
            ).pack(),
        ),
    ]
    actions_row2 = [
        InlineKeyboardButton(
            text="👤 Назначить...",
            callback_data=AdminDetailCallback(action="assign", lead_id=lead.id).pack(),
        ),
    ]
    if not getattr(lead, "assigned_admin_id", None):
        actions_row2.insert(0, InlineKeyboardButton(
            text="🙋 Взять себе",
            callback_data=AdminDetailCallback(action="assign_me", lead_id=lead.id).pack(),
        ))

    extra = []
    if status_row:
        extra.append(status_row)
    if close_row:
        extra.append(close_row)
    extra.append(prio_row)
    extra.append(actions_row1)
    extra.append(actions_row2)

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=ADMIN_LEAD_DETAIL_SCREEN_ID, text=text, keyboard=keyboard)
```

### ADMIN_COMMENT_PROMPT (`app/bot/screens/admin_comment_prompt.py`)

```python
from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_COMMENT_PROMPT_SCREEN_ID = "admin_comment_prompt"


def render_admin_comment_prompt(
    *,
    content: ContentService,
    lead_public_id: str,
    is_internal: bool,
    stack: Sequence[str],
) -> Screen:
    kind = "📝 Внутренний комментарий" if is_internal else "💬 Ответ клиенту"
    text = f"{kind} к заявке №{lead_public_id}\n\nНапишите текст одним сообщением."
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack))
    return Screen(screen_id=ADMIN_COMMENT_PROMPT_SCREEN_ID, text=text, keyboard=keyboard)
```

### ADMIN_CLOSE_REASON (`app/bot/screens/admin_close_reason.py`)

Similar to client cancel_reason but for admin REJECTED/DONE statuses.

```python
from collections.abc import Sequence
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_CLOSE_REASON_SCREEN_ID = "admin_close_reason"
CUSTOM_REASON_LABEL = "Своя причина"


class AdminCloseReasonCallback(CallbackData, prefix="adm_close"):
    action: Literal["pick", "custom", "skip"]
    lead_id: int
    target_status: str
    index: int = -1


def render_admin_close_reason(
    *,
    content: ContentService,
    lead_id: int,
    target_status: str,  # "done" or "rejected"
    stack: Sequence[str],
) -> Screen:
    is_rejected = target_status == "rejected"
    reasons = (
        content.texts.close_reasons.rejected if is_rejected
        else content.texts.close_reasons.done
    )
    extra = []
    for i, reason in enumerate(reasons):
        cb_action = "custom" if reason == CUSTOM_REASON_LABEL else "pick"
        extra.append([InlineKeyboardButton(
            text=reason,
            callback_data=AdminCloseReasonCallback(
                action=cb_action, lead_id=lead_id, target_status=target_status, index=i,
            ).pack(),
        )])
    if not is_rejected:
        # DONE: optional reason — allow skipping.
        extra.append([InlineKeyboardButton(
            text="⏭ Без причины",
            callback_data=AdminCloseReasonCallback(
                action="skip", lead_id=lead_id, target_status=target_status,
            ).pack(),
        )])

    intro = "Укажите причину отказа" if is_rejected else "Краткое резюме (можно пропустить)"
    text = f"{intro}:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=ADMIN_CLOSE_REASON_SCREEN_ID, text=text, keyboard=keyboard)
```

### ADMIN_ASSIGN_LIST (`app/bot/screens/admin_assign_list.py`)

```python
from collections.abc import Sequence
from math import ceil
from typing import Any, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.footer import nav_footer
from app.bot.ui.screen import Screen
from app.services.content import ContentService

ADMIN_ASSIGN_LIST_SCREEN_ID = "admin_assign_list"


class AdminAssignCallback(CallbackData, prefix="adm_assign"):
    action: Literal["pick", "unassign", "page"]
    lead_id: int
    admin_id: int = 0
    page: int = 1


def render_admin_assign_list(
    *,
    content: ContentService,
    lead_id: int,
    current_admin_id: int | None,
    admins: list[Any],
    page: int,
    total: int,
    page_size: int,
    stack: Sequence[str],
) -> Screen:
    total_pages = max(1, ceil(total / page_size))
    text = f"Кому назначить заявку?"
    extra = []
    if current_admin_id is not None:
        extra.append([InlineKeyboardButton(
            text="➖ Снять назначение",
            callback_data=AdminAssignCallback(
                action="unassign", lead_id=lead_id,
            ).pack(),
        )])
    for admin in admins:
        username = f"@{admin.username}" if admin.username else f"id{admin.id}"
        mark = "✓ " if current_admin_id == admin.id else ""
        extra.append([InlineKeyboardButton(
            text=f"{mark}{admin.first_name or ''} {username}".strip(),
            callback_data=AdminAssignCallback(
                action="pick", lead_id=lead_id, admin_id=admin.id,
            ).pack(),
        )])

    pagination_row = []
    if page > 1:
        pagination_row.append(InlineKeyboardButton(
            text="◀", callback_data=AdminAssignCallback(
                action="page", lead_id=lead_id, page=page - 1,
            ).pack(),
        ))
    pagination_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        pagination_row.append(InlineKeyboardButton(
            text="▶", callback_data=AdminAssignCallback(
                action="page", lead_id=lead_id, page=page + 1,
            ).pack(),
        ))
    if total_pages > 1:
        extra.append(pagination_row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=nav_footer(stack=stack, extra=extra))
    return Screen(screen_id=ADMIN_ASSIGN_LIST_SCREEN_ID, text=text, keyboard=keyboard)
```

Tests for each renderer: basic structure, callbacks pack, stack-dependent footer present. Keep tests focused.

Commit: `feat(screens): admin screens (menu/list/detail/comment/close_reason/assign)`

---

## Task 5.3 — AdminFlowState

`app/bot/states/admin_flow.py`:

```python
from aiogram.fsm.state import State, StatesGroup


class AdminFlowState(StatesGroup):
    writing_internal_comment = State()
    writing_client_reply = State()
    writing_close_reason = State()  # for DONE/REJECTED custom reason
```

Remove `AdminCommentState` from `app/bot/states/lead.py` — but keep backward-compat alias to avoid breaking imports in old admin/leads.py until that's rewritten. Simplest: leave `AdminCommentState` alone for now; the new admin_flow.py adds new states.

Commit: `feat(states): AdminFlowState with separate comment/reply/close_reason states`

---

## Task 5.4 — New admin router

`app/bot/routers/admin/menu.py`:

```python
from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.screens.admin_menu import ADMIN_MENU_SCREEN_ID, AdminMenuCallback, render_admin_menu
from app.bot.screens.admin_lead_list import ADMIN_LEAD_LIST_SCREEN_ID, AdminLeadListCallback, render_admin_lead_list
from app.bot.screens.admin_lead_detail import ADMIN_LEAD_DETAIL_SCREEN_ID, AdminDetailCallback, render_admin_lead_detail
from app.bot.screens.admin_comment_prompt import ADMIN_COMMENT_PROMPT_SCREEN_ID, render_admin_comment_prompt
from app.bot.screens.admin_close_reason import (
    ADMIN_CLOSE_REASON_SCREEN_ID, AdminCloseReasonCallback, CUSTOM_REASON_LABEL, render_admin_close_reason,
)
from app.bot.screens.admin_assign_list import (
    ADMIN_ASSIGN_LIST_SCREEN_ID, AdminAssignCallback, render_admin_assign_list,
)
from app.bot.states.admin_flow import AdminFlowState
from app.bot.ui.navigation import clear_root_message_id, get_stack, go_home, pop, push
from app.bot.ui.render import render_screen
from app.core.config import get_settings
from app.core.exceptions import AppError, PermissionDeniedError, ValidationError
from app.core.security import is_admin
from app.db.repositories.leads import LeadRepository
from app.db.repositories.users import UserRepository
from app.services.content import ContentService
from app.services.leads import LeadService
from app.services.notifications import NotificationService

router = Router(name="admin")


def _is_admin_user(current_user, settings) -> bool:
    return is_admin(current_user.telegram_id, settings)


async def _render_admin_menu(*, bot, chat_id, state, session, content, settings):
    repo = LeadRepository(session)
    counts = await repo.status_counts()
    hot = await repo.hot_count()
    await push(state, ADMIN_MENU_SCREEN_ID)
    screen = render_admin_menu(
        content=content, status_counts=counts, hot_count=hot,
        company_name=content.brand.company_name,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


@router.message(Command("admin"))
async def admin_command(
    message: Message,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await message.answer("Недостаточно прав.")
        return
    await clear_root_message_id(state)
    await go_home(state)
    await pop(state)  # remove main_menu from stack, we want admin_menu as root.
    await _render_admin_menu(
        bot=message.bot, chat_id=message.chat.id, state=state,
        session=session, content=content, settings=settings,
    )


@router.callback_query(AdminMenuCallback.filter())
async def on_admin_menu_action(
    callback: CallbackQuery,
    callback_data: AdminMenuCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    if callback_data.action == "csv":
        service = LeadService(session, settings)
        csv = await service.export_csv()
        await callback.message.answer_document(
            BufferedInputFile(csv.encode("utf-8-sig"), filename="leads.csv"),
            caption="CSV-выгрузка",
        )
        await callback.answer()
        return

    if callback_data.action == "stats":
        service = LeadService(session, settings)
        stats = await service.daily_stats()
        text = (
            f"📊 Статистика дня ({stats.date})\n\n"
            f"🆕 Новых: {stats.new}\n📞 Связались: —\n"
            f"🛠 В работе: {stats.in_progress}\n⏳ Ждут: {stats.waiting}\n"
            f"✅ Завершено: {stats.done}\n❌ Отклонено: {stats.rejected}\n🚫 Отменено: {stats.cancelled}\n\n"
            f"Топ-категория: {stats.top_category or '—'}"
        )
        await callback.message.answer(text)
        await callback.answer()
        return

    # All other actions are filtered lead lists.
    filter_label = {
        "new": "🆕 Новые",
        "contacted": "📞 Связались",
        "in_progress": "🛠 В работе",
        "waiting": "⏳ Ждут клиента",
        "hot": "🔥 Срочные",
        "all": "📋 Все заявки",
    }.get(callback_data.action, "📋 Заявки")

    is_hot = callback_data.action == "hot"
    status_filter = None if callback_data.action in ("all", "hot") else callback_data.action

    await _show_lead_list(
        bot=callback.bot, chat_id=callback.message.chat.id, state=state,
        content=content, session=session,
        status=status_filter, hot=is_hot, page=1, filter_label=filter_label,
    )
    await callback.answer()


async def _show_lead_list(*, bot, chat_id, state, content, session, status, hot, page, filter_label):
    repo = LeadRepository(session)
    page_size = content.config.ui.page_size_admin
    leads = await repo.list_by_filter(
        status=status, hot=hot, limit=page_size, offset=(page - 1) * page_size,
    )
    total = await repo.count_by_filter(status=status, hot=hot)
    await push(state, ADMIN_LEAD_LIST_SCREEN_ID)
    # Stash filter in FSM data for pagination roundtrips.
    await state.update_data(admin_filter={"status": status, "hot": hot, "label": filter_label})
    stack = await get_stack(state)
    screen = render_admin_lead_list(
        content=content, leads=leads, page=page, total=total,
        page_size=page_size, filter_label=filter_label, stack=stack,
    )
    await render_screen(bot=bot, chat_id=chat_id, state=state, screen=screen)


@router.callback_query(AdminLeadListCallback.filter())
async def on_admin_list_action(
    callback: CallbackQuery,
    callback_data: AdminLeadListCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    if callback_data.action == "page":
        data = await state.get_data()
        af = data.get("admin_filter") or {}
        await _show_lead_list(
            bot=callback.bot, chat_id=callback.message.chat.id, state=state,
            content=content, session=session,
            status=af.get("status"), hot=af.get("hot", False),
            page=callback_data.page, filter_label=af.get("label", "Заявки"),
        )
    elif callback_data.action == "open":
        repo = LeadRepository(session)
        lead = await repo.get(callback_data.lead_id)
        if lead is None:
            await callback.answer("Не найдено.", show_alert=True)
            return
        await push(state, ADMIN_LEAD_DETAIL_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen,
        )
    await callback.answer()


@router.callback_query(AdminDetailCallback.filter())
async def on_admin_detail_action(
    callback: CallbackQuery,
    callback_data: AdminDetailCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    repo = LeadRepository(session)
    service = LeadService(session, settings)

    if callback_data.action == "set_status":
        target = callback_data.value
        if target == "rejected" or target == "done":
            # Push close-reason screen.
            await push(state, ADMIN_CLOSE_REASON_SCREEN_ID)
            await state.update_data(admin_pending_status=target, admin_pending_lead=callback_data.lead_id)
            stack = await get_stack(state)
            screen = render_admin_close_reason(
                content=content, lead_id=callback_data.lead_id,
                target_status=target, stack=stack,
            )
            await render_screen(
                bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen,
            )
            await callback.answer()
            return
        # Non-terminal status change.
        try:
            lead = await service.change_status(
                lead_id=callback_data.lead_id, status=target, actor=current_user,
            )
        except AppError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        # Optionally notify client of status change.
        await NotificationService(callback.bot, settings).notify_client_status(lead)
        # Re-render detail.
        stack = await get_stack(state)
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen,
        )
        await callback.answer("Статус изменён.")
        return

    if callback_data.action == "set_priority":
        try:
            lead = await service.set_priority(
                lead_id=callback_data.lead_id, priority=callback_data.value, actor=current_user,
            )
        except AppError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        stack = await get_stack(state)
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen,
        )
        await callback.answer("Приоритет обновлён.")
        return

    if callback_data.action in ("comment_internal", "comment_reply"):
        is_internal = callback_data.action == "comment_internal"
        lead = await repo.get(callback_data.lead_id)
        if lead is None:
            await callback.answer("Не найдено.", show_alert=True)
            return
        state_target = (
            AdminFlowState.writing_internal_comment if is_internal
            else AdminFlowState.writing_client_reply
        )
        await state.set_state(state_target)
        await state.update_data(admin_comment_lead_id=callback_data.lead_id)
        await push(state, ADMIN_COMMENT_PROMPT_SCREEN_ID)
        stack = await get_stack(state)
        screen = render_admin_comment_prompt(
            content=content, lead_public_id=lead.public_id,
            is_internal=is_internal, stack=stack,
        )
        await render_screen(
            bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen,
        )
        await callback.answer()
        return

    if callback_data.action == "assign_me":
        try:
            lead = await service.reassign(
                lead_id=callback_data.lead_id, new_admin=current_user, actor=current_user,
            )
        except AppError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        stack = await get_stack(state)
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen,
        )
        await callback.answer("Назначено на вас.")
        return

    if callback_data.action == "assign":
        user_repo = UserRepository(session)
        admins = await user_repo.list_admins()
        await push(state, ADMIN_ASSIGN_LIST_SCREEN_ID)
        stack = await get_stack(state)
        lead = await repo.get(callback_data.lead_id)
        page_size = content.config.ui.page_size_admin
        screen = render_admin_assign_list(
            content=content, lead_id=callback_data.lead_id,
            current_admin_id=lead.assigned_admin_id if lead else None,
            admins=admins[:page_size], page=1, total=len(admins),
            page_size=page_size, stack=stack,
        )
        await render_screen(
            bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen,
        )
        await callback.answer()
        return


@router.callback_query(AdminCloseReasonCallback.filter())
async def on_close_reason_action(
    callback: CallbackQuery,
    callback_data: AdminCloseReasonCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    service = LeadService(session, settings)

    if callback_data.action == "custom":
        await state.set_state(AdminFlowState.writing_close_reason)
        await state.update_data(
            admin_pending_status=callback_data.target_status,
            admin_pending_lead=callback_data.lead_id,
        )
        await callback.message.answer("Напишите причину одним сообщением.")
        await callback.answer()
        return

    reason: str | None = None
    if callback_data.action == "pick":
        reasons = (
            content.texts.close_reasons.rejected if callback_data.target_status == "rejected"
            else content.texts.close_reasons.done
        )
        if callback_data.index < 0 or callback_data.index >= len(reasons):
            await callback.answer("Ошибка.", show_alert=True)
            return
        reason = reasons[callback_data.index]
    # action == "skip" → reason stays None (only allowed for DONE; rejected requires).

    if callback_data.target_status == "rejected" and reason is None:
        await callback.answer("Причина отказа обязательна.", show_alert=True)
        return

    try:
        lead = await service.change_status(
            lead_id=callback_data.lead_id,
            status=callback_data.target_status,
            actor=current_user,
            reason=reason,
        )
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await NotificationService(callback.bot, settings).notify_client_status(lead)
    # Pop close_reason screen, re-render detail.
    await pop(state)
    repo = LeadRepository(session)
    lead = await repo.get(callback_data.lead_id)
    stack = await get_stack(state)
    if lead is not None:
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen,
        )
    await callback.answer("Статус изменён.")


@router.message(StateFilter(AdminFlowState.writing_close_reason))
async def on_custom_close_reason(
    message: Message,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, напишите причину.")
        return
    data = await state.get_data()
    target_status = data.get("admin_pending_status")
    lead_id = data.get("admin_pending_lead")
    if not target_status or not lead_id:
        await message.answer("Ошибка. Начните заново.")
        await state.set_state(None)
        return
    service = LeadService(session, get_settings())
    try:
        lead = await service.change_status(
            lead_id=lead_id, status=target_status, actor=current_user, reason=text,
        )
    except AppError as exc:
        await message.answer(str(exc))
        return
    await NotificationService(message.bot, get_settings()).notify_client_status(lead)
    await state.set_state(None)
    # Re-render detail.
    repo = LeadRepository(session)
    lead = await repo.get(lead_id)
    await pop(state)  # leave close_reason screen
    stack = await get_stack(state)
    if lead is not None:
        screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
        await render_screen(
            bot=message.bot, chat_id=message.chat.id, state=state, screen=screen,
        )
    await message.answer("✅ Готово.")


@router.callback_query(AdminAssignCallback.filter())
async def on_assign_action(
    callback: CallbackQuery,
    callback_data: AdminAssignCallback,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    if not _is_admin_user(current_user, settings):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    service = LeadService(session, settings)
    user_repo = UserRepository(session)
    repo = LeadRepository(session)

    if callback_data.action == "page":
        admins = await user_repo.list_admins()
        page_size = content.config.ui.page_size_admin
        offset = (callback_data.page - 1) * page_size
        slice_ = admins[offset:offset + page_size]
        lead = await repo.get(callback_data.lead_id)
        stack = await get_stack(state)
        screen = render_admin_assign_list(
            content=content, lead_id=callback_data.lead_id,
            current_admin_id=lead.assigned_admin_id if lead else None,
            admins=slice_, page=callback_data.page, total=len(admins),
            page_size=page_size, stack=stack,
        )
        await render_screen(
            bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen,
        )
        await callback.answer()
        return

    if callback_data.action == "unassign":
        new_admin = None
    else:  # pick
        new_admin = await user_repo.get(callback_data.admin_id) if hasattr(user_repo, "get") else None
        if new_admin is None:
            from app.db.models.user import User
            new_admin = (await session.execute(
                __import__("sqlalchemy").select(User).where(User.id == callback_data.admin_id)
            )).scalar_one_or_none()
        if new_admin is None:
            await callback.answer("Админ не найден.", show_alert=True)
            return

    try:
        lead = await service.reassign(
            lead_id=callback_data.lead_id, new_admin=new_admin, actor=current_user,
        )
    except AppError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    # Notify new admin (if not self-assign).
    if new_admin is not None and new_admin.id != current_user.id:
        try:
            text = f"🔔 На вас назначена заявка №{lead.public_id}"
            await callback.bot.send_message(chat_id=new_admin.telegram_id, text=text)
        except Exception:
            pass

    # Pop assign_list, re-render detail.
    await pop(state)
    stack = await get_stack(state)
    screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
    await render_screen(
        bot=callback.bot, chat_id=callback.message.chat.id, state=state, screen=screen,
    )
    await callback.answer("Назначено.")


@router.message(StateFilter(AdminFlowState.writing_internal_comment))
@router.message(StateFilter(AdminFlowState.writing_client_reply))
async def on_admin_comment_text(
    message: Message,
    state: FSMContext,
    content: ContentService,
    session: AsyncSession,
    current_user,
) -> None:
    settings = get_settings()
    text = (message.text or "").strip()
    if not text:
        await message.answer("Комментарий не может быть пустым.")
        return
    if len(text) > 4000:
        await message.answer("Слишком длинный. Максимум 4000.")
        return
    data = await state.get_data()
    lead_id = data.get("admin_comment_lead_id")
    if not lead_id:
        await state.set_state(None)
        return
    is_internal = (await state.get_state()) == AdminFlowState.writing_internal_comment.state
    service = LeadService(session, settings)
    try:
        lead = await service.add_comment(
            lead_id=int(lead_id), admin=current_user, text=text, is_internal=is_internal,
        )
    except AppError as exc:
        await message.answer(str(exc))
        return

    if not is_internal:
        await NotificationService(message.bot, settings).notify_client_comment(lead, text)

    await state.set_state(None)
    await pop(state)  # leave comment_prompt screen
    stack = await get_stack(state)
    screen = render_admin_lead_detail(content=content, lead=lead, stack=stack)
    await render_screen(
        bot=message.bot, chat_id=message.chat.id, state=state, screen=screen,
    )
    await message.answer("✅ Сохранено.")
```

Wire the router in `app/bot/create.py` AFTER the existing `admin_leads.router` (or replace — keep both for backward-compat with `/admin`, `/new` commands during transition):

```python
from app.bot.routers.admin.menu import router as admin_menu_router
...
dispatcher.include_router(admin_menu_router)
```

Order: nav → user routers → admin_menu_router → admin_leads (legacy commands like /new can still work).

OR for clean cutover: replace `admin_leads.router` entirely with `admin_menu_router`. Then the old `/new`, `/leads`, `/leads_user`, `/leads_date` commands stop working — they're replaced by callback-driven flow from `/admin`. Step 6 will remove `admin_leads.py`. For Step 5: KEEP the legacy router included, but the new flow is via `/admin`.

Commit: `feat(bot): new admin router with full Screen-based flow`

---

## Task 5.5 — change_status requires reason for REJECTED

In `app/services/leads.py` `change_status`:

```python
    async def change_status(
        self, *, lead_id: int, status: str, actor: User, reason: str | None = None,
    ) -> Lead:
        if not is_admin(actor.telegram_id, self.settings):
            raise PermissionDeniedError("admin privileges required")
        lead = await self.get_lead(lead_id)
        if lead.status == status:
            return lead
        assert_status_transition(lead.status, status)
        if status == LeadStatus.REJECTED and not reason:
            raise ValidationError("rejection requires a reason")
        if reason is not None:
            lead.close_reason = reason
            self.session.add(lead)
            await self.session.flush()
        return await self.repository.update_status(
            lead=lead, status=status, actor_user_id=actor.id,
        )
```

Tests: `test_change_status_rejected_without_reason_raises`, `test_change_status_rejected_with_reason_persists`.

Commit: `feat(leads): require reason when status changes to REJECTED`

---

## Task 5.6 — Integration tests

`tests/integration/test_admin_flow.py`:
- `/admin` → renders admin_menu with counts
- Click "🆕 Новые" → renders admin_lead_list with status=new
- Click a lead → renders admin_lead_detail
- set_status non-terminal → status changed, detail re-rendered
- set_status REJECTED → close_reason screen pushed; pick reason → status + reason persisted
- set_priority → priority changed, detail re-rendered
- assign_me when unassigned → assigned to current user
- assign → assign_list rendered with admins
- comment_internal → comment_prompt + state set + text → comment saved (internal)
- comment_reply → same but `is_internal=False` and client notification triggered

Keep tests focused; ~10 tests covering main paths.

Commit: `test(bot): integration tests for admin flow`

---

## Step 5 Completion Checklist

- [ ] All 6 admin screens exist with tests.
- [ ] AdminFlowState exists with 3 states.
- [ ] Admin router with `/admin` command, all callback handlers.
- [ ] LeadRepository has status_counts, hot_count, list_by_filter, count_by_filter.
- [ ] UserRepository has list_admins.
- [ ] LeadService.change_status requires reason for REJECTED.
- [ ] notify_assigned admin via direct bot.send_message.
- [ ] All tests green.

Tag: `stage1-step-5-admin-ui`.

## Out of scope

- Removing legacy `app/bot/routers/admin/leads.py` and `keyboards/builders.py` — Step 6.
- `notify_new_lead` re-wired to use AdminDetailCallback — Step 6 (currently new-lead notification still uses old keyboard).
- `selectinload(LeadComment.admin)` for N+1 — Step 6.
