"""Shared fixtures. Every test gets its own data directory; nothing touches the network."""

import asyncio
import socket
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from narcisse.app import create_app
from narcisse.config import HOST, Settings
from narcisse.engine import http
from narcisse.engine.http import new_transport_client
from narcisse.engine.plugin import SourceModule
from narcisse.server import Server
from tests.fakes import FakeWhois

# Fast enough for a 30 s fake run to take 0.15 s, slow enough to pause it in between.
FAST = 200.0


class NoNetwork(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request to {request.url}")


@pytest.fixture(autouse=True)
def own_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The desktop's choices (demo or real side) go to the test's directory, never the user's."""
    monkeypatch.setenv("NARCISSE_CONFIG_DIR", str(tmp_path / "config"))


@pytest.fixture(autouse=True)
def whois(monkeypatch: pytest.MonkeyPatch) -> FakeWhois:
    """WHOIS servers for the tests that need some; any other connection is refused."""
    fake = FakeWhois()
    monkeypatch.setattr(http, "open_connection", fake.open_connection)
    return fake


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", demo=True, speed=FAST)


class Api:
    """An app with its lifespan running, and a client that talks to it like the UI does."""

    def __init__(self, app: FastAPI, client: httpx.AsyncClient, lifespan: Any) -> None:
        self.app = app
        self.client = client
        self._lifespan = lifespan
        self.stopped = False

    async def stop(self) -> None:
        """Shuts the app down as a process exit would: its runs stay as they were."""
        if not self.stopped:
            self.stopped = True
            await self.client.aclose()
            await self._lifespan.__aexit__(None, None, None)

    async def json(self, method: str, url: str, body: Any = None, status: int = 200) -> Any:
        response = await self.client.request(method, f"/api{url}", json=body)
        assert response.status_code == status, response.text
        return response.json() if response.content else None

    async def profile(self, *seeds: tuple[str, str], name: str = "Jeanne Exemple") -> int:
        profile = await self.json("POST", "/profiles", {"name": name}, status=201)
        for kind, value in seeds:
            await self.json(
                "POST", f"/profiles/{profile['id']}/seeds", {"kind": kind, "value": value}, 201
            )
        return int(profile["id"])

    async def scan(self, scan_id: int) -> Any:
        return await self.json("GET", f"/scans/{scan_id}")

    async def wait_scan(
        self, scan_id: int, until: Callable[[Any], bool], within: float = 30.0
    ) -> Any:
        # 30 s, not 10: a scan that takes 2 s alone can pass 10 s while the machine is busy (the
        # whole suite, a build); a scan that really hangs still fails long before the 120 s cap.
        async with asyncio.timeout(within):
            while True:
                scan = await self.scan(scan_id)
                if until(scan):
                    return scan
                # Not tighter: each poll reads the whole scan on the loop the scan runs on.
                await asyncio.sleep(0.05)


ApiFactory = Callable[..., Awaitable[Api]]


@pytest.fixture
async def make_api(settings: Settings) -> AsyncIterator[ApiFactory]:
    """Starts apps on demand (several in a row on the same data directory = restarts)."""
    started: list[Api] = []

    async def start(modules: dict[str, SourceModule] | None = None, **overrides: Any) -> Api:
        if modules is not None:
            # Test modules are real ones as far as the app knows: demo mode would hide them.
            overrides.setdefault("demo", False)
        # The outside world, as a test fakes it; none by default.
        transport = overrides.pop("http_transport", None) or NoNetwork()
        app = create_app(replace(settings, **overrides), modules=modules, http_transport=transport)
        lifespan = app.router.lifespan_context(app)
        await lifespan.__aenter__()
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=f"http://{HOST}:{settings.port}"
        )
        started.append(Api(app, client, lifespan))
        return started[-1]

    yield start
    for api in reversed(started):
        await api.stop()


@pytest.fixture
async def api(make_api: ApiFactory) -> Api:
    return await make_api()


@pytest.fixture
async def live_server(settings: Settings) -> AsyncIterator[str]:
    """A real uvicorn server on a free port (for streaming responses)."""
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        port = probe.getsockname()[1]
    app = create_app(replace(settings, port=port), http_transport=NoNetwork())
    config = uvicorn.Config(
        app,
        host=HOST,
        port=port,
        log_config=None,
    )
    server = Server(config)
    task = asyncio.create_task(server.serve())
    async with asyncio.timeout(10):
        while not server.started:  # noqa: ASYNC110 (uvicorn exposes a flag, not an event)
            await asyncio.sleep(0.01)
    yield f"http://{HOST}:{port}"
    server.should_exit = True
    await task


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    """The HTTP client modules get, for tests that mock the network with respx."""
    async with new_transport_client() as client:
        yield client
