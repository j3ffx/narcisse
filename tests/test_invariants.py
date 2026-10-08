"""Promises the README makes, checked (CLAUDE.md → Invariants)."""

import random
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import uvicorn
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from typer.testing import CliRunner

from narcisse import cli
from narcisse.app import NO_TELEMETRY, create_app
from narcisse.config import HOST, Settings
from narcisse.domain import EntityKind, IntrusionLevel
from narcisse.engine.plugin import Target
from narcisse.modules import discover
from narcisse.modules.demo import DemoModule, findings_for
from narcisse.storage.database import migrate
from narcisse.storage.models import Base
from tests.conftest import ApiFactory


def test_the_server_listens_on_loopback_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: dict[str, Any] = {}

    def fake_run(self: uvicorn.Server) -> None:
        seen["host"] = self.config.host

    monkeypatch.setattr(uvicorn.Server, "run", fake_run)
    monkeypatch.setenv("NARCISSE_DATA_DIR", str(tmp_path))
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        free_port = probe.getsockname()[1]
    monkeypatch.setenv("NARCISSE_PORT", str(free_port))
    result = CliRunner().invoke(cli.app, ["serve", "--no-browser"])
    assert result.exit_code == 0, result.output
    assert HOST == "127.0.0.1"
    assert seen["host"] == HOST


def test_fastapi_telemetry_is_off(settings: Settings) -> None:
    app = create_app(settings)
    for key, value in NO_TELEMETRY.items():
        assert app._telemetry[key] == value  # type: ignore[literal-required]
    assert not any(NO_TELEMETRY.values())


async def test_the_demo_module_exists_only_in_demo_mode(make_api: ApiFactory) -> None:
    normal = await make_api(None, demo=False)
    assert all(not m["demo"] for m in await normal.json("GET", "/modules"))
    demo = await make_api(None, demo=True)
    assert "demo.fake" in [m["name"] for m in await demo.json("GET", "/modules")]


@pytest.mark.parametrize("module", discover().values(), ids=lambda m: m.meta.name)
def test_every_module_describes_itself(module: Any) -> None:
    meta = module.meta
    assert meta.title
    assert meta.description
    assert meta.category
    assert meta.accepts
    assert meta.produces
    assert meta.intrusion in IntrusionLevel
    for host in meta.hosts:
        assert urlsplit(f"https://{host}").hostname == host


def test_the_demo_module_contacts_nobody_and_invents_only_reserved_names() -> None:
    assert DemoModule.meta.hosts == ()
    target = Target(
        entity_id=1, kind=EntityKind.NAME, value="Jeanne Exemple", normalized="jeanne exemple"
    )
    reserved = ("example.org", "example.net", "example.com")
    for finding in findings_for(target, random.Random(1)):
        if finding.kind == EntityKind.EMAIL:
            assert finding.value.split("@")[1] in reserved
        for url in filter(None, (finding.url, finding.value if "://" in finding.value else None)):
            host = urlsplit(url).hostname or ""
            assert host in reserved or host.endswith(tuple(f".{r}" for r in reserved)), url


def test_migrations_match_the_models(tmp_path: Path) -> None:
    path = tmp_path / "schema.sqlite3"
    migrate(path)
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []


def test_user_data_lives_outside_the_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NARCISSE_DATA_DIR", raising=False)
    monkeypatch.delenv("NARCISSE_DEV", raising=False)
    repo = Path(__file__).resolve().parents[1]
    real = Settings.from_env(demo=False).data_dir
    assert not real.resolve().is_relative_to(repo)
    # Fictitious demo profiles never land among real ones.
    assert Settings.from_env(demo=True).data_dir.name == "narcisse-demo"
    assert real.name == "narcisse"
