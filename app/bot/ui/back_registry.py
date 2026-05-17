"""Back-navigation registry.

When the user presses ⬅ Назад, ``handle_nav`` pops the stack and looks up a
back-renderer for the new top screen. The renderer re-renders that screen as
the current root (no ``push`` — ``pop`` already adjusted the stack).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

BackRenderer = Callable[..., Awaitable[None]]

_REGISTRY: dict[str, BackRenderer] = {}


def register_back(screen_id: str, renderer: BackRenderer) -> None:
    _REGISTRY[screen_id] = renderer


def get_back(screen_id: str) -> BackRenderer | None:
    return _REGISTRY.get(screen_id)


def clear() -> None:
    _REGISTRY.clear()


async def render_back(screen_id: str, **kwargs: Any) -> bool:
    """Invoke the back-renderer for ``screen_id`` if registered.

    Returns ``True`` if a renderer ran, ``False`` if none was registered.
    """
    renderer = _REGISTRY.get(screen_id)
    if renderer is None:
        return False
    await renderer(**kwargs)
    return True
