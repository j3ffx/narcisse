"""Makes the tray's native menu look like Windows 11's own: sharp, and dark when Windows is.

Without this, Windows scales the menu up like a picture on high-DPI screens (blurry), and draws it
light whatever the theme. Dark popup menus have no documented switch: uxtheme's
`SetPreferredAppMode` (ordinal 135) and `FlushMenuThemes` (136) are what Explorer, Firefox or
Notepad++ use. If they are missing, nothing happens and the menu stays light.
"""

import ctypes
import logging
import sys
from typing import Any

log = logging.getLogger(__name__)

PER_MONITOR_AWARE_V2 = -4  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
ALLOW_DARK = 1  # PreferredAppMode.AllowDark: dark when Windows' app theme is dark
SET_PREFERRED_APP_MODE = 135
FLUSH_MENU_THEMES = 136


def prepare_native_ui() -> None:
    """To call before any window exists."""
    if sys.platform != "win32":
        return
    win_dll: Any = getattr(ctypes, "WinDLL")  # noqa: B009 (Windows only, unknown to other typesheds)
    try:
        win_dll("user32").SetProcessDpiAwarenessContext(ctypes.c_void_p(PER_MONITOR_AWARE_V2))
    except (AttributeError, OSError):
        log.info("per-monitor DPI awareness unavailable; the tray menu may look blurry")
    try:
        uxtheme = win_dll("uxtheme")
        set_preferred_app_mode = uxtheme[SET_PREFERRED_APP_MODE]
        set_preferred_app_mode.argtypes = [ctypes.c_int]
        set_preferred_app_mode(ALLOW_DARK)
        uxtheme[FLUSH_MENU_THEMES]()
    except (AttributeError, OSError):
        log.info("dark menus unavailable on this Windows; the tray menu stays light")
