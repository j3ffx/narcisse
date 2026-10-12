"""What Narcisse asks of the operating system: open its window, start with the session, appear in
the Start menu. Windows first; elsewhere it falls back to a browser tab and offers no autostart."""

import importlib
import os
import subprocess
import sys
import webbrowser
from contextlib import suppress
from pathlib import Path
from typing import Any

APP_NAME = "Narcisse"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
USER_CHOICE = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
APP_PATHS = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
# Browsers that can show a page in a window of its own (`--app=`), by their Windows ProgId.
APP_MODE_BROWSERS = {
    "ChromeHTML": "chrome.exe",
    "MSEdgeHTM": "msedge.exe",
    "BraveHTML": "brave.exe",
    "VivaldiHTM": "vivaldi.exe",
}

IS_WINDOWS = sys.platform == "win32"


def _winreg() -> Any:
    """The registry module, loaded at run time: it exists only on Windows (and tests swap it)."""
    return importlib.import_module("winreg")


def windowless_python() -> Path:
    """pythonw.exe on Windows (no console window), the current interpreter elsewhere."""
    executable = Path(sys.executable)
    windowless = executable.with_name("pythonw.exe")
    return windowless if IS_WINDOWS and windowless.exists() else executable


def command(*args: str) -> list[str]:
    """How to run `narcisse <args>` without a console window."""
    return [str(windowless_python()), "-m", "narcisse", *args]


def _app_mode_browser() -> str | None:
    """The default browser's executable, if it can open a page as an app window."""
    if not IS_WINDOWS:
        return None
    winreg = _winreg()

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, USER_CHOICE) as key:
            prog_id = str(winreg.QueryValueEx(key, "ProgId")[0])
    except OSError:
        return None
    exe = next((e for p, e in APP_MODE_BROWSERS.items() if prog_id.startswith(p)), None)
    if exe is None:
        return None
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            path = str(winreg.QueryValue(root, rf"{APP_PATHS}\{exe}"))
        except OSError:
            continue
        if path and Path(path).exists():
            return path
    return None


def open_window(app_url: str, tab_url: str) -> None:
    """Narcisse in a window of its own when the default browser can, else in a new tab."""
    browser = _app_mode_browser()
    if browser:
        subprocess.Popen([browser, f"--app={app_url}"], close_fds=True)
    else:
        webbrowser.open(tab_url)


def spawn_detached(args: list[str]) -> None:
    """Starts a process that outlives this one, without a console window."""
    if IS_WINDOWS:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        subprocess.Popen(args, creationflags=flags, close_fds=True)
    else:
        subprocess.Popen(args, start_new_session=True, close_fds=True)


# Start with the session (Windows: the user's Run key, nothing machine-wide)

AUTOSTART_SUPPORTED = IS_WINDOWS


def _quote(args: list[str]) -> str:
    return subprocess.list2cmdline(args)


def autostart_enabled() -> bool:
    if not AUTOSTART_SUPPORTED:
        return False
    winreg = _winreg()

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled: bool, args: list[str]) -> None:
    """Starts `args` when the user opens their session, or stops doing so."""
    if not AUTOSTART_SUPPORTED:
        return
    winreg = _winreg()

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _quote(args))
        else:
            with suppress(FileNotFoundError):
                winreg.DeleteValue(key, APP_NAME)


# Start menu shortcut

ICON = Path(__file__).parent / "narcisse.ico"


def start_menu_shortcut() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home()))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{APP_NAME}.lnk"


def create_shortcut(args: list[str]) -> Path:
    """A Start menu entry that runs `args`. Windows only (a .lnk, written through PowerShell)."""
    if not IS_WINDOWS:
        raise RuntimeError("shortcuts are only made on Windows")
    target = start_menu_shortcut()
    # Paths go through the environment: nothing user-controlled is spliced into the script.
    env = {
        **os.environ,
        "NARCISSE_LNK": str(target),
        "NARCISSE_TARGET": args[0],
        "NARCISSE_ARGS": _quote(args[1:]),
        "NARCISSE_ICON": str(ICON),
        "NARCISSE_WORKDIR": str(Path.home()),
    }
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:NARCISSE_LNK);"
        "$s.TargetPath = $env:NARCISSE_TARGET;"
        "$s.Arguments = $env:NARCISSE_ARGS;"
        "$s.IconLocation = $env:NARCISSE_ICON;"
        "$s.WorkingDirectory = $env:NARCISSE_WORKDIR;"
        "$s.Description = 'Narcisse : ce qu''Internet sait de toi';"
        "$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        env=env,
        check=True,
        capture_output=True,
    )
    return target
