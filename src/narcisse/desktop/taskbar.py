"""Gives Narcisse's window its own place on the Windows taskbar.

The window is the browser's (`--app=`), so Windows files it under the browser: pinned, it would
relaunch the browser with its arguments, and a window opened later by Narcisse would sit next to
the pin instead of under it. Windows lets a program name a window's taskbar identity (its
AppUserModelID) and what pinning it relaunches: Narcisse sets both on its window, so the pin runs
`narcisse open` and every Narcisse window gathers under it.

Only the browser's app windows titled exactly like the page ("Narcisse") are touched: a browser
tab's window carries the browser's name in its title. Nothing is written anywhere but on the
window itself, and it goes when the window closes.
"""

import ctypes
import logging
import sys
import threading
import time
import uuid
from collections.abc import Callable
from ctypes import wintypes
from typing import Any

log = logging.getLogger(__name__)

APP_ID = "Narcisse.App"
TITLE = "Narcisse"
BROWSER_WINDOW_CLASS = "Chrome_WidgetWin_1"  # Chrome, Edge, Brave and Vivaldi alike
WAIT_SECONDS = 20.0
POLL_SECONDS = 0.25

# PKEY_AppUserModel_*: {9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}, by property id.
APP_USER_MODEL = uuid.UUID("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3")
RELAUNCH_COMMAND = 2
RELAUNCH_ICON = 3
RELAUNCH_DISPLAY_NAME = 4
ID = 5
IID_PROPERTY_STORE = uuid.UUID("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")
VT_LPWSTR = 31

# Windows' calling convention (other platforms' typesheds don't know it).
WINFUNCTYPE: Any = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)

# IPropertyStore's methods, after IUnknown's three.
GET_VALUE = 5
SET_VALUE = 6
COMMIT = 7
RELEASE = 2


class GUID(ctypes.Structure):
    _fields_ = (("bytes", ctypes.c_ubyte * 16),)

    @classmethod
    def of(cls, value: uuid.UUID) -> "GUID":
        guid = cls()
        ctypes.memmove(guid.bytes, value.bytes_le, 16)
        return guid


class PROPERTYKEY(ctypes.Structure):
    _fields_ = (("fmtid", GUID), ("pid", wintypes.DWORD))


class PROPVARIANT(ctypes.Structure):
    _fields_ = (
        ("vt", ctypes.c_ushort),
        ("reserved1", ctypes.c_ushort),
        ("reserved2", ctypes.c_ushort),
        ("reserved3", ctypes.c_ushort),
        ("value", ctypes.c_void_p),
        ("padding", ctypes.c_void_p),
    )


def _key(pid: int) -> PROPERTYKEY:
    return PROPERTYKEY(GUID.of(APP_USER_MODEL), pid)


def _method(store: ctypes.c_void_p, index: int, *argtypes: Any) -> Callable[..., int]:
    vtable = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototype = WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)
    function: Callable[..., int] = prototype(vtable[index])
    return lambda *args: function(store, *args)


def _dll(name: str) -> Any:
    return getattr(ctypes, "WinDLL")(name)  # noqa: B009 (Windows only, unknown elsewhere)


def _store(hwnd: int) -> ctypes.c_void_p | None:
    store = ctypes.c_void_p()
    iid = GUID.of(IID_PROPERTY_STORE)
    result = _dll("shell32").SHGetPropertyStoreForWindow(
        wintypes.HWND(hwnd), ctypes.byref(iid), ctypes.byref(store)
    )
    return store if result == 0 and store.value else None


def app_id(hwnd: int) -> str | None:
    """The window's taskbar identity, if one was set on it."""
    store = _store(hwnd)
    if store is None:
        return None
    try:
        value = PROPVARIANT()
        key = _key(ID)
        get = _method(store, GET_VALUE, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))
        if get(ctypes.byref(key), ctypes.byref(value)) < 0 or value.vt != VT_LPWSTR:
            return None
        text = ctypes.wstring_at(value.value) if value.value else None
        _dll("ole32").PropVariantClear(ctypes.byref(value))
        return text
    finally:
        _method(store, RELEASE)()


def brand(hwnd: int, relaunch: str, icon: str) -> bool:
    """Gives the window Narcisse's identity, and what pinning it relaunches."""
    store = _store(hwnd)
    if store is None:
        return False
    try:
        set_value = _method(
            store, SET_VALUE, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT)
        )
        # The relaunch properties first: Windows reads them when the identity changes.
        for pid, text in (
            (RELAUNCH_COMMAND, relaunch),
            (RELAUNCH_DISPLAY_NAME, TITLE),
            (RELAUNCH_ICON, icon),
            (ID, APP_ID),
        ):
            buffer = ctypes.create_unicode_buffer(text)
            value = PROPVARIANT(vt=VT_LPWSTR, value=ctypes.cast(buffer, ctypes.c_void_p).value)
            key = _key(pid)
            if set_value(ctypes.byref(key), ctypes.byref(value)) < 0:
                return False
        return _method(store, COMMIT)() >= 0
    finally:
        _method(store, RELEASE)()


def narcisse_windows() -> list[int]:
    """The browser app windows showing Narcisse."""
    user32 = _dll("user32")
    found: list[int] = []

    def visit(hwnd: int, _: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        name = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, name, 64)
        if name.value != BROWSER_WINDOW_CLASS:
            return True
        title = ctypes.create_unicode_buffer(64)
        user32.GetWindowTextW(hwnd, title, 64)
        if title.value == TITLE:
            found.append(hwnd)
        return True

    callback = WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit)
    user32.EnumWindows(callback, 0)
    return found


def brand_new_windows(relaunch: str, icon: str) -> threading.Thread | None:
    """Waits (in the background) for Narcisse's window to show its page, then gives it its
    identity. Returns the thread, for a short-lived process to wait for it."""
    if sys.platform != "win32":
        return None

    before = set(narcisse_windows())

    def watch() -> None:
        deadline = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            windows = narcisse_windows()
            for hwnd in windows:
                if app_id(hwnd) != APP_ID and brand(hwnd, relaunch, icon):
                    log.info("taskbar identity set on window %d", hwnd)
            if set(windows) - before:
                return  # the new window showed its page (and has its identity)
            time.sleep(POLL_SECONDS)
        log.info("no new Narcisse window to give a taskbar identity to")

    thread = threading.Thread(target=watch, name="taskbar", daemon=True)
    thread.start()
    return thread


def brand_shortcut(path: str) -> bool:
    """Gives a shortcut the same identity, so that pinning it from the Start menu gathers
    Narcisse's windows under the pin too."""
    if sys.platform != "win32":
        return False
    store = ctypes.c_void_p()
    iid = GUID.of(IID_PROPERTY_STORE)
    read_write = 2  # GPS_READWRITE
    result = _dll("shell32").SHGetPropertyStoreFromParsingName(
        ctypes.c_wchar_p(path), None, read_write, ctypes.byref(iid), ctypes.byref(store)
    )
    if result < 0 or not store.value:
        return False
    try:
        set_value = _method(
            store, SET_VALUE, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT)
        )
        buffer = ctypes.create_unicode_buffer(APP_ID)
        value = PROPVARIANT(vt=VT_LPWSTR, value=ctypes.cast(buffer, ctypes.c_void_p).value)
        key = _key(ID)
        if set_value(ctypes.byref(key), ctypes.byref(value)) < 0:
            return False
        return _method(store, COMMIT)() >= 0
    finally:
        _method(store, RELEASE)()
