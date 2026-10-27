"""A SearXNG instance of the user's own, with Docker, for the web search source.

`narcisse searxng`, or the settings page's button (`Launcher`), writes a `docker-compose.yml` and
SearXNG's `settings.yml` in the user's configuration directory (JSON results on, the bot limiter
off, a secret of its own: nothing secret lives in the repository), starts it on 127.0.0.1 only,
and records its address in the settings. From the app, it also opens Docker Desktop when Docker
isn't running: only ever on the user's click.
"""

import asyncio
import logging
import os
import secrets
import shutil
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import httpx
from platformdirs import user_config_path

from narcisse.preferences import Preferences

log = logging.getLogger(__name__)

PORT = 8888
IMAGE = "docker.io/searxng/searxng:latest"

COMPOSE = """\
# SearXNG for Narcisse, written by `narcisse searxng`: a metasearch engine on this machine only.
# Stop it with `docker compose down` in this folder; start it again with `docker compose up -d`.
name: narcisse-searxng
services:
  searxng:
    image: {image}
    container_name: narcisse-searxng
    ports:
      - "127.0.0.1:{port}:8080"
    volumes:
      - ./config:/etc/searxng
    environment:
      - SEARXNG_BASE_URL=http://127.0.0.1:{port}/
    restart: unless-stopped
"""

SETTINGS = """\
# Written by `narcisse searxng`: SearXNG's defaults, plus what Narcisse needs.
use_default_settings: true
server:
  secret_key: "{secret}"
  limiter: false
  image_proxy: false
search:
  formats:
    - html
    - json
"""


def directory() -> Path:
    """Where the instance's files live (the user's configuration directory)."""
    base = os.environ.get("NARCISSE_CONFIG_DIR")
    return (Path(base) if base else user_config_path("narcisse", appauthor=False)) / "searxng"


def url(port: int = PORT) -> str:
    return f"http://127.0.0.1:{port}"


def write(folder: Path, port: int = PORT) -> None:
    """Writes the compose file (again) and the settings (once: their secret stays)."""
    config = folder / "config"
    config.mkdir(parents=True, exist_ok=True)
    (folder / "docker-compose.yml").write_text(
        COMPOSE.format(image=IMAGE, port=port), encoding="utf-8", newline="\n"
    )
    settings = config / "settings.yml"
    if not settings.exists():
        settings.write_text(
            SETTINGS.format(secret=secrets.token_hex(32)), encoding="utf-8", newline="\n"
        )


def docker() -> str | None:
    return shutil.which("docker")


def _quiet() -> dict[str, Any]:
    """No console window flashing up when the tray (a windowless process) calls Docker."""
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def start(folder: Path) -> tuple[bool, str]:
    """Runs `docker compose up -d` in the folder: (whether it worked, Docker's last words)."""
    command = [docker() or "docker", "compose", "up", "-d"]
    try:
        done = subprocess.run(
            command,
            cwd=folder,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
            **_quiet(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (done.stderr or done.stdout or "").strip().splitlines()
    return done.returncode == 0, "\n".join(output[-5:])


def ready(address: str, wait: float = 90.0) -> bool:
    """Whether the instance answers a JSON search within `wait` seconds (it starts slowly)."""
    deadline = time.monotonic() + wait
    while True:
        try:
            response = httpx.get(
                f"{address}/search", params={"q": "narcisse", "format": "json"}, timeout=10
            )
            if response.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            return False
        time.sleep(2)


def daemon_up() -> bool:
    """Whether Docker's engine answers (Docker Desktop may be installed but not started)."""
    try:
        done = subprocess.run(
            [docker() or "docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            **_quiet(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0 and bool(done.stdout.strip())


def desktop_app() -> Path | None:
    """Docker Desktop, where its installer puts it (Windows, macOS); None elsewhere."""
    if sys.platform == "win32":
        for base in (os.environ.get("PROGRAMFILES"), "C:/Program Files"):
            if base and (app := Path(base) / "Docker" / "Docker" / "Docker Desktop.exe").exists():
                return app
    elif sys.platform == "darwin" and (app := Path("/Applications/Docker.app")).exists():
        return app
    return None


def open_desktop(app: Path) -> None:
    """Opens Docker Desktop, detached: it outlives Narcisse, as if the user had opened it."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", str(app)])
        return
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    subprocess.Popen([str(app)], creationflags=flags, close_fds=True)


class LaunchFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class LaunchState:
    """Where a launch from the app is: idle, starting (at `step`), ready, or failed (`error`)."""

    state: str = "idle"
    step: str | None = None  # "desktop", "compose", "waiting"
    error: str | None = None


class Launcher:
    """Installs and starts the instance when the user asks from the app: one launch at a time,
    in the background, whose progress the UI follows. The blocking calls (Docker) run in
    threads; the instance is asked through `client` (tests fake it)."""

    DOCKER_WAIT = 180.0  # Docker Desktop takes a while to start its engine
    READY_WAIT = 120.0  # SearXNG too, the first time
    POLL = 2.0

    def __init__(self, client: httpx.AsyncClient, preferences_path: Path) -> None:
        self.client = client
        self.preferences_path = preferences_path
        self.current = LaunchState()
        self._task: asyncio.Task[None] | None = None
        self._check: asyncio.Task[None] | None = None

    async def answers(self, address: str) -> bool:
        """Whether an instance answers there right now (its health check: no search is run)."""
        try:
            response = await self.client.get(f"{address}/healthz", timeout=3)
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    def autostart(self) -> None:
        """`start_if_down`, in the background: the health check mustn't hold Narcisse's start."""
        self._check = asyncio.create_task(self.start_if_down(), name="searxng-autostart")

    async def start_if_down(self) -> None:
        """On Narcisse's start: starts the instance Narcisse installed if the user asked for it
        and it doesn't answer (the machine restarted, say). An instance of their own elsewhere
        is theirs to start."""
        preferences = Preferences.load(self.preferences_path)
        if not preferences.searxng_autostart or preferences.searxng_url != url():
            return
        if not await self.answers(url()):
            log.info("SearXNG doesn't answer: starting it, as the settings ask")
            self.start()

    def start(self) -> None:
        if self.current.state == "starting":
            return  # one launch at a time
        self.current = LaunchState(state="starting")
        self._task = asyncio.create_task(self._launch(), name="searxng-launch")

    def cancel(self) -> None:
        """Stops a launch under way (the app is shutting down); Docker keeps what it started."""
        for task in (self._check, self._task):
            if task is not None and not task.done():
                task.cancel()

    async def wait(self) -> None:
        """Until the launch under way is over (for tests and shutdown)."""
        if self._check is not None:
            await asyncio.gather(self._check, return_exceptions=True)
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)

    def _step(self, step: str) -> None:
        self.current = LaunchState(state="starting", step=step)

    async def _until(self, check: Callable[[], Awaitable[bool]], wait: float) -> bool:
        deadline = time.monotonic() + wait
        while True:
            if await check():
                return True
            if time.monotonic() > deadline:
                return False
            await asyncio.sleep(self.POLL)

    async def _launch(self) -> None:
        try:
            await self._steps()
            self.current = LaunchState(state="ready")
        except LaunchFailed as failed:
            self.current = LaunchState(state="failed", error=failed.code)
        except Exception:
            log.exception("SearXNG launch failed")
            self.current = LaunchState(state="failed", error="searxng_start_failed")

    async def _steps(self) -> None:
        if docker() is None:
            raise LaunchFailed("docker_missing")
        if not await asyncio.to_thread(daemon_up):
            app = desktop_app()
            if app is None:
                raise LaunchFailed("docker_not_running")
            self._step("desktop")
            await asyncio.to_thread(open_desktop, app)
            if not await self._until(lambda: asyncio.to_thread(daemon_up), self.DOCKER_WAIT):
                raise LaunchFailed("docker_not_running")
        self._step("compose")
        folder = directory()
        await asyncio.to_thread(write, folder)
        started, said = await asyncio.to_thread(start, folder)
        if not started:
            log.warning("docker compose up failed in %s: %s", folder, said)
            raise LaunchFailed("searxng_start_failed")
        self._step("waiting")
        address = url()
        if not await self._until(lambda: self.answers(address), self.READY_WAIT):
            raise LaunchFailed("searxng_not_ready")
        preferences = Preferences.load(self.preferences_path)
        replace(preferences, searxng_url=address).save(self.preferences_path)
