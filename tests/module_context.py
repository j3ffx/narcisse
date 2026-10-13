"""Running one source module on its own, without the engine, against mocked HTTP (respx)."""

import logging
from typing import Any

import httpx

from narcisse.clock import Clock
from narcisse.domain import EntityKind
from narcisse.engine.http import DomainPacer, HttpClient
from narcisse.engine.plugin import Finding, SourceModule, Target
from narcisse.preferences import Preferences


class FakeContext:
    """What the engine gives a module (`plugin.ModuleContext`), recording what it reports."""

    def __init__(
        self,
        module: SourceModule,
        client: httpx.AsyncClient,
        *,
        preferences: Preferences | None = None,
        checkpoint: dict[str, Any] | None = None,
        target: Target | None = None,
    ) -> None:
        clock = Clock(speed=1000)
        self.preferences = preferences or Preferences()
        hosts = module.allowed_hosts(self.preferences, target)
        self.http = HttpClient(client, DomainPacer(clock), module.meta, clock, hosts)
        self.log = logging.getLogger("test-module")
        self.attempt = 1
        self.checkpoint = checkpoint
        self.saved: list[dict[str, Any]] = []
        self.notes: dict[str, int] | None = None
        self.progressed: list[tuple[int, int | None]] = []

    async def save_checkpoint(self, data: dict[str, Any]) -> None:
        self.checkpoint = data
        self.saved.append(data)

    async def progress(
        self, done: int, total: int | None, notes: dict[str, int] | None = None
    ) -> None:
        self.progressed.append((done, total))
        if notes is not None:
            self.notes = notes

    async def sleep(self, seconds: float) -> None:
        return None

    async def pause_point(self) -> None:
        return None


def target(kind: EntityKind, value: str) -> Target:
    return Target(entity_id=1, kind=kind, value=value, normalized=value.lower())


async def run(module: SourceModule, ctx: FakeContext, what: Target) -> list[Finding]:
    return [finding async for finding in module.run(ctx, what)]
