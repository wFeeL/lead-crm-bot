# Step 1 — SPA Navigation Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Создать инфраструктуру для SPA-подобной навигации — один root-message-id на пользователя, реестр экранов, навигационный стек, универсальный коллбэк `nav:back/home/cancel`, EscapeMiddleware (защита от FSM-залипаний), stale-callback guard. Существующие хендлеры пока остаются — миграция произойдёт в Step 2.

**Architecture:** Чистые data-классы (Screen) и pure-функции рендера + один универсальный коллбэк-роутер. Все state хранится в FSM data (RedisStorage уже настроен в `app/bot/create.py`). Middleware на уровне Dispatcher перехватывает `/start /menu /cancel` ДО роутеров.

**Tech Stack:** aiogram 3, FSM-storage (Redis/MemoryStorage), Pydantic 2 для callback data.

**Spec sections:** «Архитектура UX (Screen Registry)», «Защита от залипаний — три уровня», «Stale callback защита».

---

## File Structure

**Create:**
- `app/bot/ui/__init__.py` (empty marker)
- `app/bot/ui/screen.py` — `Screen` dataclass
- `app/bot/ui/callbacks.py` — `NavCallback` factory
- `app/bot/ui/footer.py` — `nav_footer(stack)` builder
- `app/bot/ui/navigation.py` — nav-stack push/pop/home/cancel
- `app/bot/ui/render.py` — `render_screen(bot, chat_id, state, screen)` (handles edit_text vs send_message lifecycle)
- `app/bot/ui/registry.py` — `SCREENS: dict[str, Callable]` registry
- `app/bot/middlewares/escape.py` — `EscapeMiddleware`
- `app/bot/ui/guards.py` — stale-callback guard utility
- `app/bot/ui/handler.py` — universal `NavCallback` handler + router

**Modify:**
- `app/bot/create.py` — register `EscapeMiddleware` + new nav router

**Test:**
- `tests/unit/test_ui_screen.py` — Screen dataclass
- `tests/unit/test_ui_callbacks.py` — NavCallback factory
- `tests/unit/test_ui_footer.py` — nav footer builder
- `tests/unit/test_ui_navigation.py` — nav-stack push/pop/home/cancel
- `tests/unit/test_ui_render.py` — render_screen lifecycle (with mocked bot)
- `tests/unit/test_ui_registry.py` — registry registration
- `tests/unit/test_ui_guards.py` — stale callback guard
- `tests/integration/test_escape_middleware.py` — EscapeMiddleware behavior on FSM

---

## Batch 1 — Pure foundation (Screen, NavCallback, footer)

Single subagent dispatch creates the value-level pieces with no telegram side-effects. Each is independently testable.

### Task 1.1 — Screen dataclass

**Files:**
- Create: `app/bot/ui/__init__.py` (empty)
- Create: `app/bot/ui/screen.py`
- Create: `tests/unit/test_ui_screen.py`

#### Step 1: Failing test

`tests/unit/test_ui_screen.py`:

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.ui.screen import Screen


def test_screen_minimal_fields():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="OK", callback_data="ok")]])
    s = Screen(screen_id="main_menu", text="Hi", keyboard=keyboard)
    assert s.screen_id == "main_menu"
    assert s.text == "Hi"
    assert s.keyboard is keyboard
    assert s.reply_keyboard is None
    assert s.next_state is None


def test_screen_is_frozen():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    s = Screen(screen_id="x", text="y", keyboard=keyboard)
    import dataclasses
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.text = "z"  # type: ignore[misc]


def test_screen_with_reply_keyboard():
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    inline = InlineKeyboardMarkup(inline_keyboard=[])
    reply = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Send")]])
    s = Screen(
        screen_id="contact_prompt",
        text="Send your phone",
        keyboard=inline,
        reply_keyboard=reply,
    )
    assert s.reply_keyboard is reply
```

Add `import pytest` at top.

#### Step 2: Run → fail (ImportError).

#### Step 3: Implement `app/bot/ui/screen.py`:

```python
from dataclasses import dataclass

from aiogram.fsm.state import State
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup


@dataclass(frozen=True)
class Screen:
    """A renderable UI screen of the bot.

    Pure value object — produced by registry functions, consumed by render().
    """

    screen_id: str
    text: str
    keyboard: InlineKeyboardMarkup
    next_state: State | None = None
    reply_keyboard: ReplyKeyboardMarkup | None = None
```

Also create empty `app/bot/ui/__init__.py`.

#### Step 4: Run → pass.

#### Step 5: Commit
```bash
git add app/bot/ui/__init__.py app/bot/ui/screen.py tests/unit/test_ui_screen.py
git commit -m "feat(ui): Screen dataclass"
```

---

### Task 1.2 — NavCallback factory

**Files:**
- Create: `app/bot/ui/callbacks.py`
- Create: `tests/unit/test_ui_callbacks.py`

#### Step 1: Failing test

```python
import pytest

from app.bot.ui.callbacks import NavCallback


def test_navcallback_pack_back():
    cb = NavCallback(action="back")
    assert cb.pack() == "nav:back"


def test_navcallback_pack_home():
    assert NavCallback(action="home").pack() == "nav:home"


def test_navcallback_pack_cancel():
    assert NavCallback(action="cancel").pack() == "nav:cancel"


def test_navcallback_unpack_roundtrip():
    s = NavCallback(action="back").pack()
    cb = NavCallback.unpack(s)
    assert cb.action == "back"


def test_navcallback_rejects_unknown_action():
    with pytest.raises(ValueError):
        NavCallback(action="teleport")
```

#### Step 2: Run → fail.

#### Step 3: Implement `app/bot/ui/callbacks.py`:

```python
from typing import Literal

from aiogram.filters.callback_data import CallbackData


class NavCallback(CallbackData, prefix="nav"):
    """Universal navigation callback.

    Three actions cover the whole nav footer:
    - back   : pop nav_stack and render previous screen
    - home   : clear nav_stack, render MAIN_MENU (does not clear FSM)
    - cancel : clear FSM state + nav_stack, render MAIN_MENU
    """

    action: Literal["back", "home", "cancel"]
```

> aiogram's `CallbackData` already validates `Literal[...]` via Pydantic. The "rejects unknown action" test asserts this guard works.

#### Step 4: Run → pass.

#### Step 5: Commit
```bash
git add app/bot/ui/callbacks.py tests/unit/test_ui_callbacks.py
git commit -m "feat(ui): NavCallback factory (back/home/cancel)"
```

---

### Task 1.3 — Footer builder

**Files:**
- Create: `app/bot/ui/footer.py`
- Create: `tests/unit/test_ui_footer.py`

#### Step 1: Failing test

```python
from aiogram.types import InlineKeyboardButton

from app.bot.ui.footer import nav_footer


def test_nav_footer_empty_stack_has_only_cancel():
    rows = nav_footer(stack=[])
    assert len(rows) == 1
    labels = [btn.text for btn in rows[0]]
    assert "🚫 Отмена" in labels
    # No back/home buttons because there's nowhere to go back.
    assert all("Назад" not in btn.text for btn in rows[0])
    assert all("Меню" not in btn.text for btn in rows[0])


def test_nav_footer_with_history_has_back_home_cancel():
    rows = nav_footer(stack=["main_menu", "faq"])
    assert len(rows) == 1
    labels = [btn.text for btn in rows[0]]
    assert any("Назад" in lbl for lbl in labels)
    assert any("Меню" in lbl for lbl in labels)
    assert any("Отмена" in lbl for lbl in labels)


def test_nav_footer_single_screen_history_has_home_cancel_no_back():
    # If stack has only main_menu, there's nothing to go back to.
    rows = nav_footer(stack=["main_menu"])
    labels = [btn.text for btn in rows[0]]
    assert all("Назад" not in lbl for lbl in labels)
    assert any("Меню" in lbl for lbl in labels) or any("Главное" in lbl for lbl in labels)


def test_nav_footer_extra_buttons_appended_above_nav():
    extra = [[InlineKeyboardButton(text="Custom", callback_data="custom:x")]]
    rows = nav_footer(stack=["main_menu", "faq"], extra=extra)
    # Extra comes first (above nav row).
    assert len(rows) == 2
    assert rows[0][0].text == "Custom"
    # Last row is the nav row.
    assert any("Назад" in btn.text for btn in rows[-1])
```

#### Step 2: Run → fail.

#### Step 3: Implement `app/bot/ui/footer.py`:

```python
from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton

from app.bot.ui.callbacks import NavCallback


def nav_footer(
    *,
    stack: Sequence[str],
    extra: Sequence[Sequence[InlineKeyboardButton]] | None = None,
) -> list[list[InlineKeyboardButton]]:
    """Build the keyboard rows for a screen, with the nav row at the bottom.

    Args:
        stack: current navigation stack (deepest = current screen).
            - len(stack) == 0: only Cancel is shown (no prior screens).
            - len(stack) == 1: Home + Cancel (no Back — already at root).
            - len(stack) >= 2: Back + Home + Cancel.
        extra: optional extra keyboard rows to prepend (e.g. screen-specific buttons).

    Returns:
        List of rows for InlineKeyboardMarkup.inline_keyboard.
    """
    rows: list[list[InlineKeyboardButton]] = []
    if extra:
        rows.extend([list(row) for row in extra])

    nav_row: list[InlineKeyboardButton] = []
    if len(stack) >= 2:
        nav_row.append(
            InlineKeyboardButton(text="⬅ Назад", callback_data=NavCallback(action="back").pack())
        )
    if len(stack) >= 1:
        nav_row.append(
            InlineKeyboardButton(text="🏠 Меню", callback_data=NavCallback(action="home").pack())
        )
    nav_row.append(
        InlineKeyboardButton(text="🚫 Отмена", callback_data=NavCallback(action="cancel").pack())
    )
    rows.append(nav_row)
    return rows
```

#### Step 4: Run → pass.

#### Step 5: Commit
```bash
git add app/bot/ui/footer.py tests/unit/test_ui_footer.py
git commit -m "feat(ui): nav_footer builder with stack-aware buttons"
```

---

## Batch 2 — Navigation core (stack, registry, render)

### Task 1.4 — Navigation stack helpers + FSM data helpers

**Files:**
- Create: `app/bot/ui/navigation.py`
- Create: `tests/unit/test_ui_navigation.py`

#### Step 1: Failing test

```python
import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from app.bot.ui.navigation import NavState, push, pop, go_home, get_stack, set_root_message_id, get_root_message_id


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


@pytest.mark.asyncio
async def test_push_appends_screen_id(state):
    await push(state, "main_menu")
    await push(state, "faq")
    assert await get_stack(state) == ["main_menu", "faq"]


@pytest.mark.asyncio
async def test_push_idempotent_for_same_top(state):
    """Pushing the same screen twice does NOT duplicate."""
    await push(state, "main_menu")
    await push(state, "main_menu")
    assert await get_stack(state) == ["main_menu"]


@pytest.mark.asyncio
async def test_pop_removes_top(state):
    await push(state, "main_menu")
    await push(state, "faq")
    popped = await pop(state)
    assert popped == "main_menu"
    assert await get_stack(state) == ["main_menu"]


@pytest.mark.asyncio
async def test_pop_on_empty_returns_none(state):
    assert await pop(state) is None
    assert await get_stack(state) == []


@pytest.mark.asyncio
async def test_pop_on_single_element_returns_same_and_keeps_main_menu(state):
    """Popping when only root remains keeps the root (you can't go back further)."""
    await push(state, "main_menu")
    popped = await pop(state)
    assert popped == "main_menu"
    assert await get_stack(state) == ["main_menu"]


@pytest.mark.asyncio
async def test_go_home_clears_stack_to_main_menu(state):
    await push(state, "main_menu")
    await push(state, "faq")
    await push(state, "faq_answer")
    await go_home(state)
    assert await get_stack(state) == ["main_menu"]


@pytest.mark.asyncio
async def test_root_message_id_setter_and_getter(state):
    assert await get_root_message_id(state) is None
    await set_root_message_id(state, 12345)
    assert await get_root_message_id(state) == 12345
```

#### Step 2: Run → fail.

#### Step 3: Implement `app/bot/ui/navigation.py`:

```python
from aiogram.fsm.context import FSMContext

# FSM data keys used by the SPA navigation infrastructure.
NAV_STACK_KEY = "nav_stack"
ROOT_MESSAGE_ID_KEY = "root_message_id"

MAIN_MENU_SCREEN_ID = "main_menu"


class NavState:
    """Type-level marker — currently a namespace for FSM-data keys.

    Kept as a class for forward compatibility; instances are not used.
    """


async def get_stack(state: FSMContext) -> list[str]:
    data = await state.get_data()
    return list(data.get(NAV_STACK_KEY, []))


async def push(state: FSMContext, screen_id: str) -> None:
    """Append screen_id to the nav stack unless it equals the current top."""
    stack = await get_stack(state)
    if stack and stack[-1] == screen_id:
        return
    stack.append(screen_id)
    await state.update_data({NAV_STACK_KEY: stack})


async def pop(state: FSMContext) -> str | None:
    """Pop the top screen and return it.

    If the stack has only one element (the root), do not actually pop —
    return the root as the "destination" so the caller knows to stay there.
    """
    stack = await get_stack(state)
    if not stack:
        return None
    if len(stack) == 1:
        return stack[0]
    stack.pop()
    await state.update_data({NAV_STACK_KEY: stack})
    return stack[-1]


async def go_home(state: FSMContext) -> None:
    """Replace the stack with just [MAIN_MENU_SCREEN_ID]."""
    await state.update_data({NAV_STACK_KEY: [MAIN_MENU_SCREEN_ID]})


async def get_root_message_id(state: FSMContext) -> int | None:
    data = await state.get_data()
    value = data.get(ROOT_MESSAGE_ID_KEY)
    return int(value) if value is not None else None


async def set_root_message_id(state: FSMContext, message_id: int) -> None:
    await state.update_data({ROOT_MESSAGE_ID_KEY: int(message_id)})


async def clear_root_message_id(state: FSMContext) -> None:
    """Drop the root message id (e.g. after sending a fresh root message)."""
    data = await state.get_data()
    if ROOT_MESSAGE_ID_KEY in data:
        del data[ROOT_MESSAGE_ID_KEY]
        await state.set_data(data)
```

#### Step 4: Run → pass.

#### Step 5: Commit
```bash
git add app/bot/ui/navigation.py tests/unit/test_ui_navigation.py
git commit -m "feat(ui): nav-stack and root_message_id FSM helpers"
```

---

### Task 1.5 — Stale callback guard

**Files:**
- Create: `app/bot/ui/guards.py`
- Create: `tests/unit/test_ui_guards.py`

#### Step 1: Failing test

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.ui.guards import is_root_message


@pytest.mark.asyncio
async def test_is_root_message_true_when_match():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.message_id = 123
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"root_message_id": 123})
    assert await is_root_message(cb, state) is True


@pytest.mark.asyncio
async def test_is_root_message_false_when_stale():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.message_id = 999
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"root_message_id": 123})
    assert await is_root_message(cb, state) is False


@pytest.mark.asyncio
async def test_is_root_message_false_when_no_root_yet():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.message_id = 123
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    # No root_message_id stored — treat as stale (callback from before SPA init).
    assert await is_root_message(cb, state) is False


@pytest.mark.asyncio
async def test_is_root_message_false_when_callback_has_no_message():
    cb = MagicMock()
    cb.message = None
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"root_message_id": 123})
    assert await is_root_message(cb, state) is False
```

#### Step 2: Run → fail.

#### Step 3: Implement `app/bot/ui/guards.py`:

```python
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.ui.navigation import ROOT_MESSAGE_ID_KEY


async def is_root_message(callback: CallbackQuery, state: FSMContext) -> bool:
    """Return True when the callback originated from the current root message.

    A False value usually means the user tapped a button on an old (stale)
    message after the root has moved. Callers should respond with an alert
    and re-render the current root instead of processing the callback.
    """
    if callback.message is None:
        return False
    data = await state.get_data()
    root_id = data.get(ROOT_MESSAGE_ID_KEY)
    if root_id is None:
        return False
    return int(root_id) == int(callback.message.message_id)
```

#### Step 4: Run → pass.

#### Step 5: Commit
```bash
git add app/bot/ui/guards.py tests/unit/test_ui_guards.py
git commit -m "feat(ui): stale-callback guard via root_message_id"
```

---

### Task 1.6 — Screen registry

**Files:**
- Create: `app/bot/ui/registry.py`
- Create: `tests/unit/test_ui_registry.py`

#### Step 1: Failing test

```python
import pytest
from aiogram.types import InlineKeyboardMarkup

from app.bot.ui.registry import SCREENS, register_screen, get_renderer
from app.bot.ui.screen import Screen


def test_register_and_get():
    def renderer() -> Screen:
        return Screen(
            screen_id="custom",
            text="x",
            keyboard=InlineKeyboardMarkup(inline_keyboard=[]),
        )
    register_screen("custom", renderer)
    assert get_renderer("custom") is renderer
    # Cleanup so the test is repeatable.
    del SCREENS["custom"]


def test_register_rejects_duplicate():
    def renderer() -> Screen:
        return Screen(
            screen_id="dup", text="x",
            keyboard=InlineKeyboardMarkup(inline_keyboard=[]),
        )
    register_screen("dup", renderer)
    with pytest.raises(ValueError, match="already registered"):
        register_screen("dup", renderer)
    del SCREENS["dup"]


def test_get_renderer_missing_raises():
    with pytest.raises(KeyError, match="unknown_screen"):
        get_renderer("unknown_screen")
```

#### Step 2: Run → fail.

#### Step 3: Implement `app/bot/ui/registry.py`:

```python
from collections.abc import Callable
from typing import Any

# Renderers receive context via kwargs and return a Screen synchronously OR async.
# For Step 1 we keep the signature loose (Any) — Step 2 will narrow per-screen.
ScreenRenderer = Callable[..., Any]

SCREENS: dict[str, ScreenRenderer] = {}


def register_screen(screen_id: str, renderer: ScreenRenderer) -> None:
    """Register a renderer for a screen id. Raises if already registered."""
    if screen_id in SCREENS:
        raise ValueError(f"screen {screen_id!r} already registered")
    SCREENS[screen_id] = renderer


def get_renderer(screen_id: str) -> ScreenRenderer:
    """Look up a renderer. Raises KeyError if not registered."""
    if screen_id not in SCREENS:
        raise KeyError(screen_id)
    return SCREENS[screen_id]
```

#### Step 4: Run → pass.

#### Step 5: Commit
```bash
git add app/bot/ui/registry.py tests/unit/test_ui_registry.py
git commit -m "feat(ui): Screen registry"
```

---

### Task 1.7 — render_screen lifecycle

**Files:**
- Create: `app/bot/ui/render.py`
- Create: `tests/unit/test_ui_render.py`

#### Step 1: Failing test

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from app.bot.ui.navigation import set_root_message_id
from app.bot.ui.render import render_screen
from app.bot.ui.screen import Screen


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


@pytest.mark.asyncio
async def test_render_first_time_sends_new_message(state):
    bot = MagicMock()
    sent = MagicMock(message_id=555)
    bot.send_message = AsyncMock(return_value=sent)
    bot.edit_message_text = AsyncMock()

    screen = Screen(screen_id="main_menu", text="Hi", keyboard=InlineKeyboardMarkup(inline_keyboard=[]))
    await render_screen(bot=bot, chat_id=42, state=state, screen=screen)

    bot.send_message.assert_awaited_once()
    bot.edit_message_text.assert_not_called()
    data = await state.get_data()
    assert data["root_message_id"] == 555


@pytest.mark.asyncio
async def test_render_second_time_edits_existing_root(state):
    await set_root_message_id(state, 100)
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()

    screen = Screen(screen_id="faq", text="Q", keyboard=InlineKeyboardMarkup(inline_keyboard=[]))
    await render_screen(bot=bot, chat_id=42, state=state, screen=screen)

    bot.edit_message_text.assert_awaited_once()
    bot.send_message.assert_not_called()
    call_kwargs = bot.edit_message_text.await_args.kwargs
    assert call_kwargs["chat_id"] == 42
    assert call_kwargs["message_id"] == 100
    assert call_kwargs["text"] == "Q"


@pytest.mark.asyncio
async def test_render_falls_back_to_send_when_edit_fails(state):
    """If edit_message_text raises (e.g. message deleted), send a fresh one."""
    from aiogram.exceptions import TelegramBadRequest

    await set_root_message_id(state, 100)
    bot = MagicMock()
    bot.edit_message_text = AsyncMock(
        side_effect=TelegramBadRequest(method=MagicMock(), message="message to edit not found")
    )
    sent = MagicMock(message_id=200)
    bot.send_message = AsyncMock(return_value=sent)

    screen = Screen(screen_id="x", text="y", keyboard=InlineKeyboardMarkup(inline_keyboard=[]))
    await render_screen(bot=bot, chat_id=42, state=state, screen=screen)

    bot.edit_message_text.assert_awaited_once()
    bot.send_message.assert_awaited_once()
    data = await state.get_data()
    assert data["root_message_id"] == 200
```

#### Step 2: Run → fail.

#### Step 3: Implement `app/bot/ui/render.py`:

```python
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from app.bot.ui.navigation import get_root_message_id, set_root_message_id
from app.bot.ui.screen import Screen

logger = logging.getLogger(__name__)


async def render_screen(
    *,
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    screen: Screen,
) -> int:
    """Render the screen on the user's root message, or send a new one.

    Returns the resulting message_id (root). Updates FSM data root_message_id.

    Reply-keyboard is intentionally NOT handled here — screens that need one
    (contact prompt, file upload) are responsible for sending a separate
    prompt message after this call.
    """
    root_id = await get_root_message_id(state)
    if root_id is not None:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=root_id,
                text=screen.text,
                reply_markup=screen.keyboard,
            )
            return root_id
        except TelegramBadRequest as exc:
            logger.info("root_message_edit_failed_falling_back_to_send: %s", exc)

    sent = await bot.send_message(
        chat_id=chat_id,
        text=screen.text,
        reply_markup=screen.keyboard,
    )
    await set_root_message_id(state, sent.message_id)
    return sent.message_id
```

#### Step 4: Run tests
```
.venv/bin/pytest tests/unit/test_ui_render.py -v
```

If `TelegramBadRequest` constructor signature differs, adjust the test mock — read `aiogram.exceptions` to see the actual init signature. The contract is: render_screen falls back to send when edit raises ANY `TelegramBadRequest`. Test should be adjusted to whatever constructor pattern works.

#### Step 5: Commit
```bash
git add app/bot/ui/render.py tests/unit/test_ui_render.py
git commit -m "feat(ui): render_screen lifecycle (edit-or-send root)"
```

---

## Batch 3 — Middleware + universal handler + dispatcher wiring

### Task 1.8 — EscapeMiddleware

**Files:**
- Create: `app/bot/middlewares/escape.py`
- Create: `tests/integration/test_escape_middleware.py`

#### Step 1: Failing test

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from app.bot.middlewares.escape import EscapeMiddleware


class _DummyState(StatesGroup):
    waiting = State()


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


def _message(text: str):
    msg = MagicMock()
    msg.text = text
    msg.chat = MagicMock(id=42)
    msg.from_user = MagicMock(id=42)
    return msg


@pytest.mark.asyncio
async def test_escape_clears_fsm_on_slash_cancel(state):
    await state.set_state(_DummyState.waiting)
    handler = AsyncMock()
    middleware = EscapeMiddleware()

    msg = _message("/cancel")
    data = {"state": state}
    await middleware(handler, msg, data)

    assert await state.get_state() is None
    handler.assert_not_awaited()  # Middleware short-circuits the rest of the chain.


@pytest.mark.asyncio
async def test_escape_clears_fsm_on_slash_menu(state):
    await state.set_state(_DummyState.waiting)
    handler = AsyncMock()
    msg = _message("/menu")
    await EscapeMiddleware()(handler, msg, {"state": state})
    assert await state.get_state() is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_escape_clears_fsm_on_slash_start(state):
    await state.set_state(_DummyState.waiting)
    handler = AsyncMock()
    msg = _message("/start")
    await EscapeMiddleware()(handler, msg, {"state": state})
    assert await state.get_state() is None
    # /start passes through so the start handler can render MAIN_MENU as a fresh root.
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_escape_passthrough_for_normal_message(state):
    handler = AsyncMock()
    msg = _message("hello")
    await EscapeMiddleware()(handler, msg, {"state": state})
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_escape_passthrough_when_no_fsm_state(state):
    """If the user types /cancel without an active FSM state, just pass through —
    the regular handler will render MAIN_MENU."""
    handler = AsyncMock()
    msg = _message("/cancel")
    await EscapeMiddleware()(handler, msg, {"state": state})
    handler.assert_awaited_once()  # Pass through.
```

#### Step 2: Run → fail.

#### Step 3: Implement `app/bot/middlewares/escape.py`:

```python
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject

# Commands that should always free the user from an FSM-stuck state.
ESCAPE_COMMANDS = ("/cancel", "/menu", "/start")


class EscapeMiddleware(BaseMiddleware):
    """When the user types /cancel, /menu, or /start while an FSM state is active,
    clear that state so the user can recover from a stuck flow.

    - /cancel and /menu — short-circuit the chain (the regular handler does not run).
      The user should land on MAIN_MENU; the menu router can register a handler that
      fires on the absence of state (it will not, because we don't call the handler).
      Specifically: callers must register a /cancel and /menu handler at the top of
      the menu router so it renders MAIN_MENU. The middleware ensures the FSM is
      clean before that handler runs.

    Actually — to keep the interface clean — /cancel and /menu DO pass through to
    the rest of the chain, BUT the FSM is cleared first. This way:
        - /cancel handler in the menu router clears the draft and renders MAIN_MENU.
        - /menu handler does the same.
        - /start handler creates a fresh root and renders MAIN_MENU.

    Update: Re-reading the tests above:
        /cancel and /menu: state cleared, handler NOT called (test expects no call).
        /start: state cleared, handler IS called (test expects single call).

    So /cancel and /menu are FULL ESCAPES — they don't continue the chain. The
    rendering of MAIN_MENU on /cancel/menu happens in a dedicated short-circuit
    section of this middleware (or here we just clear state and rely on a fallback
    handler if any). For Step 1 (no MAIN_MENU yet) we only test the clearing
    behavior, not the rendering.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        text = getattr(event, "text", None)
        if not isinstance(event, Message) and not (hasattr(event, "text") and event.text is not None):
            # Non-message events pass through.
            return await handler(event, data)

        if text not in ESCAPE_COMMANDS:
            return await handler(event, data)

        state: FSMContext | None = data.get("state")
        if state is not None:
            await state.set_state(None)
            # Clear FSM data too — fresh start.
            await state.set_data({})

        if text == "/start":
            # /start always continues to the normal start handler.
            return await handler(event, data)

        # /cancel and /menu short-circuit: they do not invoke downstream handlers.
        # Step 2 will add a MAIN_MENU rendering hook here. For now, return None.
        return None
```

Wait — looking at the test for `/start`: handler IS called. For `/cancel` and `/menu`: handler is NOT called. The implementation must split these.

> Note for implementer: the comment block in the code is exploratory — clean it up. The final code should be brief and match the test exactly:
>
> - For `/start`: clear FSM, then pass through.
> - For `/cancel` or `/menu`: clear FSM, then return None (short-circuit).
> - For any other message: pass through unchanged.
> - For non-Message events: pass through unchanged.

Cleaner version:

```python
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject

ESCAPE_COMMANDS = ("/cancel", "/menu", "/start")


class EscapeMiddleware(BaseMiddleware):
    """Clears FSM state when the user issues /start, /menu, or /cancel.

    /start passes through to the regular start handler.
    /cancel and /menu short-circuit (no downstream handler is invoked).
    Step 2 will add a render hook so /cancel and /menu return the user to MAIN_MENU.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.text not in ESCAPE_COMMANDS:
            return await handler(event, data)

        state: FSMContext | None = data.get("state")
        if state is not None:
            await state.set_state(None)
            await state.set_data({})

        if event.text == "/start":
            return await handler(event, data)
        return None
```

#### Step 4: Run tests → all pass.

#### Step 5: Commit
```bash
git add app/bot/middlewares/escape.py tests/integration/test_escape_middleware.py
git commit -m "feat(bot): EscapeMiddleware clears FSM on /start /menu /cancel"
```

---

### Task 1.9 — Universal NavCallback handler + register in dispatcher

**Files:**
- Create: `app/bot/ui/handler.py`
- Modify: `app/bot/create.py` — register `EscapeMiddleware` + `nav_router`

#### Step 1: Write the universal handler

Create `app/bot/ui/handler.py`:

```python
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.ui.callbacks import NavCallback
from app.bot.ui.navigation import go_home, pop

nav_router = Router(name="nav")


@nav_router.callback_query(NavCallback.filter())
async def handle_nav(
    callback: CallbackQuery,
    callback_data: NavCallback,
    state: FSMContext,
) -> None:
    """Universal navigation: back / home / cancel.

    Step 1 only implements the FSM-state side. Rendering MAIN_MENU is the
    responsibility of Step 2 (when MAIN_MENU exists). For Step 1 the handler:

    - back   : pops the nav stack (handler in Step 2 will re-render previous screen).
    - home   : clears the stack down to MAIN_MENU.
    - cancel : clears FSM state entirely + clears the stack.

    All three answer the callback so Telegram clears the spinner.
    """
    if callback_data.action == "back":
        await pop(state)
    elif callback_data.action == "home":
        await go_home(state)
    elif callback_data.action == "cancel":
        await state.set_state(None)
        await state.set_data({})

    # Acknowledge so the user's button doesn't show a spinner forever.
    await callback.answer()
```

> Note: rendering is intentionally deferred. Step 2's MAIN_MENU implementation will hook into this handler (likely by importing it and patching or by composing — TBD in Step 2 plan). For now the handler just manages state.

#### Step 2: Update `app/bot/create.py` to wire EscapeMiddleware and nav_router

In `app/bot/create.py`, modify `create_dispatcher`:

```python
def create_dispatcher(settings: Settings, redis: Redis | None = None) -> Dispatcher:
    storage = (
        RedisStorage(
            redis=redis,
            state_ttl=timedelta(hours=settings.fsm_ttl_hours),
            data_ttl=timedelta(hours=settings.fsm_ttl_hours),
        )
        if redis is not None
        else MemoryStorage()
    )
    dispatcher = Dispatcher(storage=storage)

    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(DbSessionMiddleware())
        observer.outer_middleware(UserMiddleware(settings))

    # EscapeMiddleware runs on messages only (after outer middlewares so it has
    # access to FSM context via the standard pipeline).
    dispatcher.message.middleware(EscapeMiddleware())

    dispatcher.message.middleware(RateLimitMiddleware(redis, settings, event_type="message"))
    dispatcher.callback_query.middleware(
        RateLimitMiddleware(redis, settings, event_type="callback")
    )

    # Universal nav handler must be registered BEFORE feature routers so it
    # short-circuits navigation callbacks before any feature-specific handler.
    dispatcher.include_router(nav_router)
    dispatcher.include_router(lead_create.router)
    dispatcher.include_router(my_leads.router)
    dispatcher.include_router(admin_leads.router)
    dispatcher.include_router(start.router)
    return dispatcher
```

Add imports at top:
```python
from app.bot.middlewares.escape import EscapeMiddleware
from app.bot.ui.handler import nav_router
```

#### Step 3: Smoke test — dispatcher creates without error

Add to `tests/integration/test_escape_middleware.py` (or a new test file):

```python
def test_dispatcher_creation_includes_nav_router():
    from app.bot.create import create_dispatcher
    from app.core.config import Settings
    settings = Settings(_env_file=None, bot_token="123:abc")
    dispatcher = create_dispatcher(settings, redis=None)
    # Nav router should be in the dispatcher's chain
    router_names = [r.name for r in dispatcher.sub_routers]
    assert "nav" in router_names
```

#### Step 4: Run
```
.venv/bin/pytest tests/unit/test_ui_callbacks.py tests/unit/test_ui_navigation.py tests/integration/test_escape_middleware.py -v
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format app/bot/middlewares/escape.py app/bot/ui/handler.py app/bot/create.py
```

#### Step 5: Commit
```bash
git add app/bot/ui/handler.py app/bot/create.py tests/integration/test_escape_middleware.py
git commit -m "feat(bot): universal NavCallback handler + register with dispatcher"
```

---

## Step 1 Completion Checklist

- [ ] `.venv/bin/pytest -q` — green.
- [ ] `.venv/bin/ruff check .` — green.
- [ ] `app/bot/ui/__init__.py` exists.
- [ ] `Screen` dataclass importable from `app.bot.ui.screen`.
- [ ] `NavCallback` importable from `app.bot.ui.callbacks`.
- [ ] `nav_footer` builds rows with appropriate buttons based on stack depth.
- [ ] `push`, `pop`, `go_home`, `get_stack`, `get_root_message_id`, `set_root_message_id` work on FSMContext.
- [ ] `is_root_message` returns False for stale callbacks.
- [ ] `SCREENS` registry has `register_screen` / `get_renderer`.
- [ ] `render_screen` edits root on existing root_id, falls back to send.
- [ ] `EscapeMiddleware` clears FSM on `/start`, `/menu`, `/cancel`; only `/start` continues chain.
- [ ] `nav_router` registered in dispatcher BEFORE feature routers.

Tag after final review:
```bash
git tag stage1-step-1-spa-foundation
```

## Out of scope

- Actually rendering MAIN_MENU on `/cancel`, `/menu`, or `nav:home/cancel` — Step 2 (which adds MAIN_MENU itself).
- Migrating any existing handler to use the new infrastructure — Step 2.
- Stale-callback guard usage in existing handlers — Step 2/3.
