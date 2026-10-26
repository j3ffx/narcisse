"""SearXNG installed and started from the app, with Docker faked (no container is ever run)."""

from pathlib import Path

import httpx
import pytest

from narcisse import searxng
from tests.conftest import Api, ApiFactory


class FakeDocker:
    """Docker as the launch sees it: installed or not, its engine up or not, Desktop opening."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, installed: bool = True) -> None:
        self.up = False
        self.desktop: Path | None = Path("Docker Desktop.exe")
        self.opened = 0
        self.composed: list[Path] = []
        self.compose_works = True
        monkeypatch.setattr(searxng, "docker", lambda: "docker" if installed else None)
        monkeypatch.setattr(searxng, "daemon_up", lambda: self.up)
        monkeypatch.setattr(searxng, "desktop_app", lambda: self.desktop)
        monkeypatch.setattr(searxng, "open_desktop", self._open)
        monkeypatch.setattr(searxng, "start", self._compose)
        monkeypatch.setattr(searxng.Launcher, "POLL", 0.0)

    def _open(self, app: Path) -> None:
        self.opened += 1
        self.up = True  # Desktop started its engine

    def _compose(self, folder: Path) -> tuple[bool, str]:
        self.composed.append(folder)
        return self.compose_works, "" if self.compose_works else "port is already allocated"


def instance(answers: bool = True) -> httpx.MockTransport:
    """127.0.0.1:8888, where the instance answers its health check (or nothing does)."""

    def handle(request: httpx.Request) -> httpx.Response:
        if answers and request.url.host == "127.0.0.1" and request.url.path == "/healthz":
            return httpx.Response(200, text="OK")
        raise httpx.ConnectError("nothing listens there")

    return httpx.MockTransport(handle)


async def launch(api: Api) -> dict[str, object]:
    started = await api.json("POST", "/searxng/start", {}, status=202)
    assert started["state"] == "starting"
    await api.app.state.services.searxng.wait()
    status: dict[str, object] = await api.json("GET", "/searxng")
    return status


async def test_a_launch_opens_docker_desktop_starts_searxng_and_sets_its_address(
    make_api: ApiFactory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeDocker(monkeypatch)
    api = await make_api(None, demo=False, http_transport=instance())

    status = await launch(api)

    assert status == {
        "docker": True,
        "address": "http://127.0.0.1:8888",
        "running": True,
        "state": "ready",
        "step": None,
        "error": None,
    }
    assert fake.opened == 1
    # The instance's files went to the user's configuration directory, a secret of their own.
    [folder] = fake.composed
    assert folder == tmp_path / "config" / "searxng"
    assert (folder / "docker-compose.yml").exists()
    assert "secret_key" in (folder / "config" / "settings.yml").read_text(encoding="utf-8")
    preferences = await api.json("GET", "/preferences")
    assert preferences["searxng_url"] == "http://127.0.0.1:8888"


async def test_docker_already_running_is_left_alone(
    make_api: ApiFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeDocker(monkeypatch)
    fake.up = True
    api = await make_api(None, demo=False, http_transport=instance())
    assert (await launch(api))["state"] == "ready"
    assert fake.opened == 0


@pytest.mark.parametrize(
    ("setup", "error"),
    [
        ("missing", "docker_missing"),
        ("no_desktop", "docker_not_running"),
        ("compose_fails", "searxng_start_failed"),
        ("never_answers", "searxng_not_ready"),
    ],
)
async def test_a_launch_that_fails_says_why(
    make_api: ApiFactory, monkeypatch: pytest.MonkeyPatch, setup: str, error: str
) -> None:
    fake = FakeDocker(monkeypatch, installed=setup != "missing")
    fake.up = setup in ("compose_fails", "never_answers")
    if setup == "no_desktop":
        fake.desktop = None
    if setup == "compose_fails":
        fake.compose_works = False
    monkeypatch.setattr(searxng.Launcher, "READY_WAIT", 0.0)
    api = await make_api(None, demo=False, http_transport=instance(setup != "never_answers"))

    status = await launch(api)

    assert (status["state"], status["error"]) == ("failed", error)
    assert (await api.json("GET", "/preferences"))["searxng_url"] is None


async def test_the_status_says_whether_an_instance_answers(
    make_api: ApiFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    FakeDocker(monkeypatch)
    api = await make_api(None, demo=False, http_transport=instance(answers=False))
    status = await api.json("GET", "/searxng")
    assert (status["running"], status["state"], status["address"]) == (False, "idle", None)


async def test_demo_mode_never_starts_anything(
    make_api: ApiFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeDocker(monkeypatch)
    api = await make_api(None, demo=True, http_transport=instance())
    await api.json("POST", "/searxng/start", {}, status=409)
    assert (fake.opened, fake.composed) == (0, [])
