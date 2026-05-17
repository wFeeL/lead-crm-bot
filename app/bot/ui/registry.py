from collections.abc import Callable
from typing import Any

ScreenRenderer = Callable[..., Any]

SCREENS: dict[str, ScreenRenderer] = {}


def register_screen(screen_id: str, renderer: ScreenRenderer) -> None:
    """Register a renderer for a screen id. Raises ValueError if already registered."""
    if screen_id in SCREENS:
        raise ValueError(f"screen {screen_id!r} already registered")
    SCREENS[screen_id] = renderer


def get_renderer(screen_id: str) -> ScreenRenderer:
    """Look up a renderer. Raises KeyError if not registered."""
    if screen_id not in SCREENS:
        raise KeyError(screen_id)
    return SCREENS[screen_id]
