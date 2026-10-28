"""Scans a profile asks for on its own, what changed since the previous scan, and the command
that starts a scan from cron or the Task Scheduler."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import httpx
import pytest
from sqlalchemy import update
from typer.testing import CliRunner

from narcisse import cli
from narcisse.config import Settings
from narcisse.domain import EntityKind
from narcisse.engine import schedule
from narcisse.engine.plugin import Finding, ModuleContext, ModuleMeta, SourceModule, Target
from narcisse.engine.schedule import ProfileState
from narcisse.storage.models import Scan
from tests.conftest import Api, ApiFactory
from tests.fakes import meta

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def state(profile_id: int, rescan: str, days_ago: float | None, busy: bool = False) -> ProfileState:
    last = NOW - timedelta(days=days_ago) if days_ago is not None else None
    return ProfileState(profile_id=profile_id, rescan=rescan, last_scan=last, busy=busy)


def test_a_profile_is_due_once_its_interval_has_passed() -> None:
    assert schedule.due([state(1, "weekly", 8)], NOW, False) == 1
    assert schedule.due([state(1, "weekly", 6)], NOW, False) is None
    assert schedule.due([state(1, "monthly", 29)], NOW, False) is None
    assert schedule.due([state(1, "monthly", 31)], NOW, False) == 1
    assert schedule.due([state(1, "never", 400)], NOW, False) is None


def test_never_next_to_another_scan_and_the_most_overdue_first() -> None:
    assert schedule.due([state(1, "weekly", 8, busy=True)], NOW, False) is None
    assert schedule.due([state(1, "weekly", 8)], NOW, scheduled_running=True) is None
    assert schedule.due([state(1, "weekly", None)], NOW, False) is None  # never scanned
    assert schedule.due([state(1, "weekly", 8), state(2, "monthly", 40)], NOW, False) == 2


def test_the_next_scan_is_its_interval_after_the_last() -> None:
    assert schedule.next_scan("weekly", NOW) == NOW + timedelta(days=7)
    assert schedule.next_scan("never", NOW) is None
    assert schedule.next_scan("monthly", None) is None


class Pages(SourceModule):
    meta: ClassVar[ModuleMeta] = meta("test.pages")

    def __init__(self) -> None:
        self.pages = ["https://a.example.org/jeanne"]

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(0, 1)
        for url in self.pages:
            yield Finding(kind=EntityKind.URL, value=url, relation="mentioned_on", url=url)


async def scanned(api: Api, profile: int) -> dict[str, Any]:
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    done: dict[str, Any] = await api.wait_scan(scan["id"], lambda s: s["status"] == "done")
    return done


async def test_the_engine_starts_the_scans_that_are_due(make_api: ApiFactory) -> None:
    pages = Pages()
    api = await make_api({"test.pages": pages})
    profile = await api.profile(("username", "jeanne"))
    await api.json(
        "PATCH", f"/profiles/{profile}", {"settings": {"rescan": "weekly", "pivot_depth": 0}}
    )
    first = await scanned(api, profile)
    assert "changes" not in (first["notes"] or {})  # nothing to compare the first one with
    assert await api.json("POST", "/schedule/due", {}) is None  # not due yet

    services = api.app.state.services
    async with services.db.write() as session:
        week_ago = services.engine.clock.now() - timedelta(days=8)
        await session.execute(update(Scan).values(created_at=week_ago))

    pages.pages.append("https://b.example.org/jeanne")
    due = await api.json("POST", "/schedule/due", {})
    assert due["notes"] == {"scheduled": True}
    assert await api.json("POST", "/schedule/due", {}) is None  # one at a time
    done = await api.wait_scan(due["id"], lambda s: s["status"] == "done")
    assert done["notes"]["changes"] == {"new": 1, "gone": 0, "modified": 0}
    assert await api.json("POST", "/schedule/due", {}) is None  # just scanned


async def test_a_profile_that_never_asks_is_left_alone(make_api: ApiFactory) -> None:
    api = await make_api({"test.pages": Pages()})
    profile = await api.profile(("username", "jeanne"))
    await scanned(api, profile)
    services = api.app.state.services
    async with services.db.write() as session:
        await session.execute(update(Scan).values(created_at=datetime(2020, 1, 1, tzinfo=UTC)))
    assert await api.json("POST", "/schedule/due", {}) is None


async def test_the_command_starts_a_scan_and_says_what_changed(
    live_server: str, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = int(live_server.rsplit(":", 1)[1])
    monkeypatch.setattr(cli, "_locate", lambda port_, demo: (replace(settings, port=port), True))
    monkeypatch.setattr(cli, "SCAN_POLL_SECONDS", 0.05)
    async with httpx.AsyncClient(base_url=f"{live_server}/api") as client:
        profile = (await client.post("/profiles", json={"name": "Jeanne Exemple"})).json()
        await client.post(
            f"/profiles/{profile['id']}/seeds", json={"kind": "username", "value": "jeanne"}
        )

    result = await asyncio.to_thread(
        CliRunner().invoke, cli.app, ["scan", "--profil", str(profile["id"]), "--demo"]
    )
    assert result.exit_code == 0, result.output
    assert "Scan de « Jeanne Exemple » lancé" in result.output
    assert "Scan terminé" in result.output

    none_due = await asyncio.to_thread(CliRunner().invoke, cli.app, ["scan", "--demo"])
    assert none_due.exit_code == 0
    assert "Aucun scan programmé" in none_due.output
