"""Modules whose behaviour tests control precisely."""

import asyncio
from collections.abc import AsyncIterator
from typing import ClassVar

from narcisse import notes
from narcisse.domain import SEED_KINDS, EntityKind
from narcisse.engine.plugin import (
    Finding,
    InputRejected,
    ModuleContext,
    ModuleMeta,
    SourceModule,
    Target,
)


def meta(name: str, *, parallel: int = 4) -> ModuleMeta:
    return ModuleMeta(
        name=name,
        title=name,
        description="Test module.",
        category="test",
        accepts=SEED_KINDS,
        produces=frozenset({EntityKind.URL}),
        max_parallel_runs=parallel,
    )


class Steps(SourceModule):
    """`steps` findings, one every `delay` (clock) seconds, resuming from its checkpoint."""

    meta: ClassVar[ModuleMeta] = meta("test.steps")

    def __init__(self, steps: int = 10, delay: float = 1.0) -> None:
        self.steps = steps
        self.delay = delay
        self.started_at_step: list[int] = []
        self.running = 0
        self.max_running = 0

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        first = int((ctx.checkpoint or {}).get("step", 0))
        self.started_at_step.append(first)
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        try:
            for step in range(first, self.steps):
                await ctx.progress(step, self.steps, {"checked": step})
                await ctx.sleep(self.delay)
                url = f"https://steps.example.org/{target.normalized}/{step}"
                yield Finding(kind=EntityKind.URL, value=url, relation="mentioned_on", url=url)
                await ctx.save_checkpoint({"step": step + 1})
            # The final report always goes through (progress events are spaced out).
            await ctx.progress(self.steps, self.steps, {"checked": self.steps})
        finally:
            self.running -= 1


class OneAtATime(Steps):
    meta: ClassVar[ModuleMeta] = meta("test.one_at_a_time", parallel=1)


class Crashes(SourceModule):
    meta: ClassVar[ModuleMeta] = meta("test.crashes")

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        raise RuntimeError("bug in a module")
        yield  # pragma: no cover


class Rejects(SourceModule):
    meta: ClassVar[ModuleMeta] = meta("test.rejects")

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        raise InputRejected("input_rejected")
        yield  # pragma: no cover


class Profiles(SourceModule):
    """Finds an account for the username, then a site and a name read on that account: the
    shape of a real profile source."""

    meta: ClassVar[ModuleMeta] = meta("test.profiles")

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        account = f"https://social.example.org/@{target.normalized}"
        yield Finding(kind=EntityKind.ACCOUNT, value=account, relation="has_account", url=account)
        via = (EntityKind.ACCOUNT, account)
        yield Finding(
            kind=EntityKind.URL,
            value="https://jeanne.example.org",
            relation="links_to",
            url=account,
            via=via,
        )
        yield Finding(
            kind=EntityKind.NAME,
            value="Jeanne Exemple",
            relation="shows_name",
            url=account,
            via=via,
        )
        # A trace that was never yielded: the target stands in.
        yield Finding(
            kind=EntityKind.EMAIL,
            value="jeanne@example.org",
            relation="shows_email",
            url=account,
            via=(EntityKind.ACCOUNT, "https://elsewhere.example.org/jeanne"),
        )


class FakeWhois:
    """WHOIS servers that answer from a table: (server, query) → text. Any other connection is
    refused, as no test may reach the network."""

    def __init__(self) -> None:
        self.answers: dict[tuple[str, str], str] = {}
        self.asked: list[tuple[str, str]] = []

    async def open_connection(self, host: str, port: int) -> tuple[asyncio.StreamReader, "_Writer"]:
        if port != 43 or not any(server == host for server, _ in self.answers):
            raise ConnectionRefusedError(f"no fake WHOIS server for {host}:{port}")
        reader = asyncio.StreamReader()
        return reader, _Writer(self, host, reader)


class _Writer:
    def __init__(self, whois: FakeWhois, host: str, reader: asyncio.StreamReader) -> None:
        self._whois, self._host, self._reader = whois, host, reader

    def write(self, data: bytes) -> None:
        query = data.decode().strip()
        self._whois.asked.append((self._host, query))
        self._reader.feed_data(self._whois.answers.get((self._host, query), "").encode())
        self._reader.feed_eof()

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None


def said(finding: Finding) -> str:
    """What a finding's proof says, in French (its note, then the text read on the page)."""
    return notes.text(finding.note, finding.excerpt, "fr") or ""
