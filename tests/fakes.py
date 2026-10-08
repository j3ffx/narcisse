"""Modules whose behaviour tests control precisely."""

from collections.abc import AsyncIterator
from typing import ClassVar

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
                await ctx.progress(step, self.steps)
                await ctx.sleep(self.delay)
                url = f"https://steps.example.org/{target.normalized}/{step}"
                yield Finding(kind=EntityKind.URL, value=url, relation="mentioned_on", url=url)
                await ctx.save_checkpoint({"step": step + 1})
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
