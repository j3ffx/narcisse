"""`narcisse tray`: the server in the background, an icon in the notification area.

The icon shows whether something runs, waits or failed, its menu opens Narcisse, pauses every scan,
restarts or quits, and Windows notifications say when a scan ends or a search fails. It reads the
same API as the UI, over loopback, every two seconds.
"""

import json
import logging
import threading
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pystray
import uvicorn

from narcisse.app import create_app
from narcisse.config import HOST, Settings
from narcisse.desktop import mode, system
from narcisse.desktop.art import TrayState, tray_icon
from narcisse.desktop.state import Summary, notifications, reminder_notice, summarize
from narcisse.server import Server

log = logging.getLogger(__name__)

POLL_SECONDS = 2.0


class Preferences:
    """The tray's own settings, next to the data they concern."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self.notifications: bool = bool(data.get("notifications", True))
        # The day the tray last said that requests wait for a reminder (once a day at most).
        reminded = data.get("reminded_on")
        self.reminded_on: str | None = reminded if isinstance(reminded, str) else None

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"notifications": self.notifications, "reminded_on": self.reminded_on}
        self.path.write_text(json.dumps(data), encoding="utf-8")


class Tray:
    def __init__(self, settings: Settings, *, open_on_start: bool) -> None:
        self.settings = settings
        self.api = f"http://{HOST}:{settings.port}/api"
        self.open_on_start = open_on_start
        self.prefs = Preferences(settings.data_dir / "desktop.json")
        self.summary = summarize(None)
        self.activity: dict[str, Any] | None = None
        self.stopping = threading.Event()
        self.server = Server(
            uvicorn.Config(
                create_app(settings),
                host=HOST,
                port=settings.port,
                log_config=None,
                access_log=False,
                timeout_graceful_shutdown=3,
            )
        )
        self.server_thread = threading.Thread(target=self.server.run, name="server", daemon=True)
        self.icon = pystray.Icon(
            "narcisse", tray_icon(TrayState.IDLE), self.summary.tooltip, self._menu()
        )
        self._shown_state = TrayState.IDLE
        self._checked_on: str | None = None

    # What a restart runs again: this side. (The start with Windows opens the side chosen last.)
    @property
    def tray_args(self) -> list[str]:
        return ["tray", "--demo" if self.settings.demo else "--real"]

    def _menu(self) -> pystray.Menu:
        item = pystray.MenuItem
        return pystray.Menu(
            item("Ouvrir Narcisse", self.open, default=True),
            item(lambda _: self.summary.tooltip.removeprefix("Narcisse : "), None, enabled=False),
            pystray.Menu.SEPARATOR,
            item(
                "Mettre en pause les scans en cours",
                self.pause_all,
                enabled=lambda _: bool(self.summary.running_scans),
            ),
            item(
                "Notifications",
                self.toggle_notifications,
                checked=lambda _: self.prefs.notifications,
            ),
            item(
                "Mode démo",
                self.toggle_demo,
                checked=lambda _: self.settings.demo,
            ),
            item(
                "Démarrer avec Windows",
                self.toggle_autostart,
                checked=lambda _: system.autostart_enabled(),
                visible=system.AUTOSTART_SUPPORTED,
            ),
            pystray.Menu.SEPARATOR,
            item("Redémarrer", self.restart),
            item("Quitter", self.quit),
        )

    def run(self) -> None:
        self.server_thread.start()
        self.icon.run(setup=self._setup)

    def _setup(self, icon: pystray.Icon) -> None:
        icon.visible = True
        threading.Thread(target=self._watch, name="tray-watch", daemon=True).start()

    def _watch(self) -> None:
        with httpx.Client(timeout=5) as client:
            while not self.stopping.is_set():
                if not self.server_thread.is_alive():
                    self._server_gone(client)
                    return
                try:
                    activity = client.get(f"{self.api}/activity").json()
                except (httpx.HTTPError, ValueError):
                    activity = None
                if activity is not None:
                    self._show(activity)
                    self._remind(client)
                    if self.open_on_start:
                        self.open_on_start = False
                        self.open()
                self.stopping.wait(POLL_SECONDS)

    def _server_gone(self, client: httpx.Client) -> None:
        """The server stopped on its own. Two clicks in a row on the shortcut start two trays: the
        second loses the port to the first, which then serves alone; anything else is a failure."""
        try:
            other = client.get(f"{self.api}/info").status_code == 200
        except httpx.HTTPError:
            other = False
        if other:
            if self.open_on_start:
                self.open()
        else:
            self.icon.notify("Narcisse s’est arrêté. Le détail est dans son journal.")
            self.stopping.wait(5)
        self.icon.stop()

    def _show(self, activity: dict[str, Any]) -> None:
        if self.prefs.notifications:
            for note in notifications(self.activity, activity):
                self.icon.notify(note.message, note.title)
        self.activity = activity
        summary: Summary = summarize(activity)
        if summary.state != self._shown_state:
            self.icon.icon = tray_icon(summary.state)
            self._shown_state = summary.state
        if summary != self.summary:
            self.summary = summary
            self.icon.title = summary.tooltip
            self.icon.update_menu()

    def _remind(self, client: httpx.Client) -> None:
        """Once a day, says how many sent requests wait for a reminder (a month without an
        answer)."""
        today = date.today().isoformat()
        if self._checked_on == today:
            return
        self._checked_on = today
        if not self.prefs.notifications or self.prefs.reminded_on == today:
            return
        try:
            count = int(client.get(f"{self.api}/requests/due").json()["count"])
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return
        if message := reminder_notice(count):
            self.icon.notify(message, "Narcisse")
            self.prefs.reminded_on = today
            self.prefs.save()

    # Menu actions (pystray calls them from its own thread)

    def open(self, *_: object) -> None:
        system.open_window(self.settings.app_url, self.settings.url)

    def pause_all(self, *_: object) -> None:
        with httpx.Client(timeout=5) as client:
            for scan_id in self.summary.running_scans:
                try:
                    client.post(f"{self.api}/scans/{scan_id}/pause")
                except httpx.HTTPError:
                    log.exception("could not pause scan %s", scan_id)

    def toggle_notifications(self, *_: object) -> None:
        self.prefs.notifications = not self.prefs.notifications
        self.prefs.save()

    def toggle_autostart(self, *_: object) -> None:
        system.set_autostart(not system.autostart_enabled(), system.command("tray"))

    def _stop_server(self) -> None:
        self.stopping.set()
        self.server.should_exit = True
        self.server_thread.join(timeout=15)

    def restart(self, *_: object) -> None:
        """Picks up new code (after a `git pull` and a build) and runs it."""
        self._stop_server()
        system.spawn_detached(system.command(*self.tray_args))
        self.icon.stop()

    def toggle_demo(self, *_: object) -> None:
        """Switches between the demo and the user's own data: remembered for the Start menu entry
        and the start with Windows, and Narcisse starts again on the other side, in a window."""
        demo = not self.settings.demo
        mode.remember(demo)
        self._stop_server()
        system.spawn_detached(system.command("tray", "--open", "--demo" if demo else "--real"))
        self.icon.stop()

    def quit(self, *_: object) -> None:
        self._stop_server()
        self.icon.stop()
