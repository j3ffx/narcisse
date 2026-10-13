"""A SearXNG instance of the user's own, with Docker, for the web search source.

`narcisse searxng` writes a `docker-compose.yml` and SearXNG's `settings.yml` in the user's
configuration directory (JSON results on, the bot limiter off, a secret of its own: nothing secret
lives in the repository), starts it on 127.0.0.1 only, and records its address in the settings.
"""

import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

import httpx
from platformdirs import user_config_path

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


def start(folder: Path) -> tuple[bool, str]:
    """Runs `docker compose up -d` in the folder: (whether it worked, Docker's last words)."""
    command = [docker() or "docker", "compose", "up", "-d"]
    try:
        done = subprocess.run(
            command, cwd=folder, capture_output=True, text=True, timeout=900, check=False
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
