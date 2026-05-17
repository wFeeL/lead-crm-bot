from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import Message
from app.bot.middlewares.escape import EscapeMiddleware


class _DummyState(StatesGroup):
    waiting = State()


@pytest.fixture
async def state():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=42, user_id=42)
    return FSMContext(storage=storage, key=key)


def _message(text: str) -> Message:
    """Build a MagicMock that passes the isinstance(event, Message) check."""
    msg = MagicMock(spec=Message)
    msg.text = text
    return msg


async def test_escape_clears_fsm_on_slash_cancel(state: FSMContext):
    await state.set_state(_DummyState.waiting)
    handler = AsyncMock()
    msg = _message("/cancel")
    # Pass state only (no content/user/session) — middleware short-circuits after FSM clear.
    await EscapeMiddleware()(handler, msg, {"state": state})
    # State cleared; render hook gracefully no-ops without context.
    assert await state.get_state() is None
    handler.assert_not_awaited()
    # Don't assert any bot send — middleware early-returns when context is incomplete.


async def test_escape_clears_fsm_on_slash_menu(state: FSMContext):
    await state.set_state(_DummyState.waiting)
    handler = AsyncMock()
    msg = _message("/menu")
    # Pass state only (no content/user/session) — middleware short-circuits after FSM clear.
    await EscapeMiddleware()(handler, msg, {"state": state})
    # State cleared; render hook gracefully no-ops without context.
    assert await state.get_state() is None
    handler.assert_not_awaited()
    # Don't assert any bot send — middleware early-returns when context is incomplete.


async def test_escape_clears_fsm_on_slash_start_but_continues(state: FSMContext):
    await state.set_state(_DummyState.waiting)
    handler = AsyncMock()
    msg = _message("/start")
    await EscapeMiddleware()(handler, msg, {"state": state})
    assert await state.get_state() is None
    handler.assert_awaited_once()


async def test_escape_passthrough_for_normal_message(state: FSMContext):
    handler = AsyncMock()
    msg = _message("hello")
    await EscapeMiddleware()(handler, msg, {"state": state})
    handler.assert_awaited_once()


async def test_escape_short_circuits_slash_cancel_without_active_fsm(state: FSMContext):
    """/cancel without active FSM still short-circuits (consistent behavior)."""
    handler = AsyncMock()
    msg = _message("/cancel")
    await EscapeMiddleware()(handler, msg, {"state": state})
    handler.assert_not_awaited()  # Still short-circuits per spec.


async def test_escape_passthrough_for_non_message_event(state: FSMContext):
    handler = AsyncMock()
    # CallbackQuery, for example — should pass through.
    cb = MagicMock()  # Not isinstance Message.
    await EscapeMiddleware()(handler, cb, {"state": state})
    handler.assert_awaited_once()


def test_dispatcher_includes_nav_router_before_feature_routers():
    """Verify create_dispatcher wires nav_router first by inspecting source structure.

    Calling create_dispatcher() twice in the same process causes RuntimeError because
    aiogram router objects (module-level singletons in feature modules) can only be
    attached to one Dispatcher. We therefore verify the ordering structurally instead
    of calling create_dispatcher a second time.
    """
    import ast
    import inspect

    import app.bot.create as create_module

    source = inspect.getsource(create_module.create_dispatcher)
    tree = ast.parse(source)

    # Collect all dispatcher.include_router(...) call argument names in order.
    included: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
        ):
            arg = node.args[0]
            # e.g. include_router(create_nav_router()) or include_router(nav_router)
            if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
                included.append(arg.func.id)
            elif isinstance(arg, ast.Name):
                included.append(arg.id)
            elif isinstance(arg, ast.Attribute):
                included.append(arg.attr)

    assert included, "No include_router calls found in create_dispatcher"
    # nav factory/router must appear first
    assert included[0] in ("create_nav_router", "nav_router"), (
        f"Expected nav router first, got: {included}"
    )
    # menu_router must also be included
    assert "menu_router" in included, f"menu_router not found in included routers: {included}"
