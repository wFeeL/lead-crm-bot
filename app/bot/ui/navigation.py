from aiogram.fsm.context import FSMContext

NAV_STACK_KEY = "nav_stack"
ROOT_MESSAGE_ID_KEY = "root_message_id"
MAIN_MENU_SCREEN_ID = "main_menu"


async def get_stack(state: FSMContext) -> list[str]:
    data = await state.get_data()
    return list(data.get(NAV_STACK_KEY, []))


async def push(state: FSMContext, screen_id: str) -> None:
    """Append screen_id unless it equals the current top (idempotent)."""
    stack = await get_stack(state)
    if stack and stack[-1] == screen_id:
        return
    stack.append(screen_id)
    await state.update_data({NAV_STACK_KEY: stack})


async def pop(state: FSMContext) -> str | None:
    """Pop the top screen and return the new top (the destination).

    Edge cases:
    - Empty stack → None.
    - Single-element stack → return that element without popping (can't go further back).
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
    """Reset stack to just [MAIN_MENU_SCREEN_ID]."""
    await state.update_data({NAV_STACK_KEY: [MAIN_MENU_SCREEN_ID]})


async def get_root_message_id(state: FSMContext) -> int | None:
    data = await state.get_data()
    value = data.get(ROOT_MESSAGE_ID_KEY)
    return int(value) if value is not None else None


async def set_root_message_id(state: FSMContext, message_id: int) -> None:
    await state.update_data({ROOT_MESSAGE_ID_KEY: int(message_id)})
