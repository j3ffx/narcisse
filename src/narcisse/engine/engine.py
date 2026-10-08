"""The scan engine: schedules module runs, stores their findings as they come, survives restarts.

A scan is a set of module runs (one module × one input entity). Every state lives in SQLite and
every change is an event, so that the UI, a reopened browser or a restarted process all see the
same thing. Runs execute as asyncio tasks, bounded globally and per module; per-domain pacing is
the HTTP client's job.
"""

import asyncio
import hashlib
import logging
from collections import Counter
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from narcisse.clock import Clock
from narcisse.domain import (
    FINISHED_RUN_STATUSES,
    EntityKind,
    EntityStatus,
    RunStatus,
    ScanStatus,
    SeedStatus,
)
from narcisse.engine.events import EventBus, Transaction
from narcisse.engine.http import DomainPacer, HttpClient
from narcisse.engine.plugin import (
    Finding,
    ModuleError,
    ModuleMeta,
    RateLimited,
    SourceModule,
    Target,
    TransientError,
)
from narcisse.errors import AppError, not_found
from narcisse.normalize import normalize
from narcisse.schemas import EntityOut, ResultOut, RunOut, ScanDetail, ScanOut
from narcisse.storage.models import Edge, Entity, Evidence, ModuleRun, Profile, Scan

log = logging.getLogger(__name__)

MAX_PARALLEL_RUNS = 8
# Transient errors (network, 5xx) are retried by the engine itself, after 5 s then 10 s.
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 5.0
# Progress events of one run are spaced out (the last one always goes through).
PROGRESS_INTERVAL = 0.25

IDENTITY_KEY = "self"
WAITING = (RunStatus.QUEUED, RunStatus.RATE_LIMITED)
ACTIVE = (RunStatus.QUEUED, RunStatus.RATE_LIMITED, RunStatus.RUNNING, RunStatus.PAUSED)


def scan_out(scan: Scan) -> ScanOut:
    return ScanOut.model_validate({**_columns(scan, ScanOut), "profile_name": scan.profile.name})


def scan_detail(scan: Scan) -> ScanDetail:
    return ScanDetail.model_validate(
        {
            **_columns(scan, ScanDetail),
            "profile_name": scan.profile.name,
            "runs": [RunOut.of(run) for run in scan.runs],
        }
    )


def _columns(obj: Any, schema: type[ScanOut]) -> dict[str, Any]:
    return {k: getattr(obj, k) for k in schema.model_fields if k in obj.__table__.columns}


async def upsert_entity(
    session: AsyncSession,
    *,
    profile_id: int,
    kind: EntityKind,
    display: str,
    normalized: str,
    now: datetime,
    status: EntityStatus = EntityStatus.UNREVIEWED,
    confidence: float | None = None,
) -> Entity:
    entity = await session.scalar(
        select(Entity).where(
            Entity.profile_id == profile_id,
            Entity.kind == kind,
            Entity.normalized == normalized,
        )
    )
    if entity is None:
        entity = Entity(
            profile_id=profile_id,
            kind=kind,
            normalized=normalized,
            display=display,
            status=status,
            confidence=confidence,
            attributes={},
            first_seen=now,
            last_seen=now,
        )
        session.add(entity)
        await session.flush()
    else:
        entity.last_seen = now
        if confidence is not None:
            entity.confidence = max(entity.confidence or 0.0, confidence)
    return entity


async def upsert_edge(
    session: AsyncSession,
    *,
    profile_id: int,
    source_id: int,
    target_id: int,
    relation: str,
    module: str,
    now: datetime,
    confidence: float | None = None,
) -> Edge:
    edge = await session.scalar(
        select(Edge).where(
            Edge.source_id == source_id,
            Edge.target_id == target_id,
            Edge.relation == relation,
            Edge.module == module,
        )
    )
    if edge is None:
        edge = Edge(
            profile_id=profile_id,
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            module=module,
            confidence=confidence,
            first_seen=now,
            last_seen=now,
        )
        session.add(edge)
        await session.flush()
    else:
        edge.last_seen = now
        if confidence is not None:
            edge.confidence = max(edge.confidence or 0.0, confidence)
    return edge


class RunContext:
    """What a running module sees of the engine (see `plugin.ModuleContext`)."""

    def __init__(self, engine: "Engine", run: ModuleRun, meta: ModuleMeta) -> None:
        self._engine = engine
        self._run_id = run.id
        self._scan_id = run.scan_id
        self.http = HttpClient(engine.http_client, engine.pacer, meta, engine.clock)
        self.log = logging.getLogger(f"narcisse.modules.{meta.name}")
        self.attempt = run.attempts
        self.checkpoint = run.checkpoint
        self._last_progress = 0.0

    async def save_checkpoint(self, data: dict[str, Any]) -> None:
        self.checkpoint = data
        await self._engine.db.shielded(self._save_checkpoint(data))

    async def _save_checkpoint(self, data: dict[str, Any]) -> None:
        async with self._engine.db.write() as session:
            await session.execute(
                update(ModuleRun).where(ModuleRun.id == self._run_id).values(checkpoint=data)
            )

    async def progress(self, done: int, total: int | None) -> None:
        loop = asyncio.get_running_loop()
        if done != total and loop.time() - self._last_progress < PROGRESS_INTERVAL:
            return
        self._last_progress = loop.time()
        await self._engine.db.shielded(self._progress(done, total))

    async def _progress(self, done: int, total: int | None) -> None:
        async with self._engine.bus.transaction() as tx:
            await tx.session.execute(
                update(ModuleRun)
                .where(ModuleRun.id == self._run_id)
                .values(progress_done=done, progress_total=total)
            )
            tx.emit(
                "run.progress",
                {"run_id": self._run_id, "done": done, "total": total},
                self._scan_id,
            )

    async def pause_point(self) -> None:
        await self._engine.gate(self._scan_id).wait()

    async def sleep(self, seconds: float) -> None:
        await self.pause_point()
        await self._engine.clock.sleep(seconds)
        await self.pause_point()


class Engine:
    def __init__(
        self,
        bus: EventBus,
        modules: dict[str, SourceModule],
        http_client: httpx.AsyncClient,
        *,
        max_parallel_runs: int = MAX_PARALLEL_RUNS,
    ) -> None:
        self.bus = bus
        self.db = bus.db
        self.clock: Clock = bus.clock
        self.modules = modules
        self.http_client = http_client
        self.pacer = DomainPacer(self.clock)
        self.max_parallel_runs = max_parallel_runs
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._task_modules: dict[int, str] = {}
        self._gates: dict[int, asyncio.Event] = {}
        self._wake = asyncio.Event()
        self._dispatcher: asyncio.Task[None] | None = None
        self._stopping = False

    # Life cycle

    async def start(self) -> None:
        """Picks up where the last process stopped: interrupted runs go back to the queue."""
        async with self.bus.transaction() as tx:
            runs = await tx.session.scalars(
                select(ModuleRun).where(ModuleRun.status == RunStatus.RUNNING)
            )
            for run in runs:
                self._set_status(tx, run, RunStatus.QUEUED)
            paused = await tx.session.scalars(
                select(Scan.id).where(Scan.status == ScanStatus.PAUSED)
            )
            for scan_id in paused:
                self.gate(scan_id).clear()
        self._dispatcher = asyncio.create_task(self._dispatch_loop(), name="engine-dispatcher")

    async def stop(self) -> None:
        """Stops every task, leaving their runs as they are: the next start resumes them."""
        self._stopping = True
        tasks = [t for t in (self._dispatcher, *self._tasks.values()) if t is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def gate(self, scan_id: int) -> asyncio.Event:
        """Set while the scan may run; cleared while it is paused."""
        gate = self._gates.get(scan_id)
        if gate is None:
            gate = self._gates[scan_id] = asyncio.Event()
            gate.set()
        return gate

    # Commands

    async def start_scan(self, profile_id: int, module_names: list[str] | None) -> ScanDetail:
        now = self.clock.now()
        async with self.bus.transaction() as tx:
            profile = await tx.session.get(Profile, profile_id)
            if profile is None:
                raise not_found("profile")
            seeds = [s for s in profile.seeds if s.status == SeedStatus.WATCH]
            if not seeds:
                raise AppError("no_seeds", status=409)
            names = module_names or profile.settings.get("modules") or list(self.modules)
            unknown = [n for n in names if n not in self.modules]
            if unknown:
                raise AppError("unknown_module", status=422, params={"modules": unknown})

            identity = await upsert_entity(
                tx.session,
                profile_id=profile.id,
                kind=EntityKind.IDENTITY,
                display=profile.name,
                normalized=IDENTITY_KEY,
                now=now,
                status=EntityStatus.CONFIRMED,
                confidence=1.0,
            )
            identity.display = profile.name
            scan = Scan(
                profile=profile,
                status=ScanStatus.RUNNING,
                modules=names,
                results_count=0,
                created_at=now,
                finished_at=None,
            )
            tx.session.add(scan)
            await tx.session.flush()
            for seed in seeds:
                entity = await upsert_entity(
                    tx.session,
                    profile_id=profile.id,
                    kind=EntityKind(seed.kind),
                    display=seed.value,
                    normalized=seed.normalized,
                    now=now,
                    status=EntityStatus.CONFIRMED,
                    confidence=1.0,
                )
                await upsert_edge(
                    tx.session,
                    profile_id=profile.id,
                    source_id=identity.id,
                    target_id=entity.id,
                    relation="declares",
                    module="seed",
                    now=now,
                    confidence=1.0,
                )
                for name in names:
                    if seed.kind in self.modules[name].meta.accepts:
                        tx.session.add(
                            ModuleRun(
                                scan_id=scan.id,
                                module=name,
                                input_entity=entity,
                                status=RunStatus.QUEUED,
                                results_count=0,
                                attempts=0,
                                retryable=False,
                                created_at=now,
                                updated_at=now,
                            )
                        )
            await tx.session.flush()
            await tx.session.refresh(scan, ["runs"])
            if not scan.runs:
                raise AppError("nothing_to_scan", status=409)
            detail = scan_detail(scan)
            tx.emit("scan.created", detail, scan.id)
        self._wake.set()
        return detail

    async def pause(self, scan_id: int) -> None:
        async with self.bus.transaction() as tx:
            scan = await self._scan(tx.session, scan_id)
            if scan.status != ScanStatus.RUNNING:
                raise AppError("scan_not_running", status=409)
            self.gate(scan_id).clear()
            scan.status = ScanStatus.PAUSED
            for run in scan.runs:
                if run.status in ACTIVE:
                    self._set_status(tx, run, RunStatus.PAUSED)
            tx.emit("scan.updated", scan_out(scan), scan.id)

    async def resume(self, scan_id: int) -> None:
        async with self.bus.transaction() as tx:
            scan = await self._scan(tx.session, scan_id)
            if scan.status != ScanStatus.PAUSED:
                raise AppError("scan_not_paused", status=409)
            scan.status = ScanStatus.RUNNING
            for run in scan.runs:
                if run.status == RunStatus.PAUSED:
                    self._set_status(tx, run, self._resumed_status(run))
            tx.emit("scan.updated", scan_out(scan), scan.id)
            await self._refresh_scan(tx, scan)
        self.gate(scan_id).set()
        self._wake.set()

    async def cancel(self, scan_id: int) -> None:
        async with self.bus.transaction() as tx:
            scan = await self._scan(tx.session, scan_id)
            if scan.status not in (ScanStatus.RUNNING, ScanStatus.PAUSED):
                raise AppError("scan_finished", status=409)
            scan.status = ScanStatus.CANCELLED
            scan.finished_at = self.clock.now()
            for run in scan.runs:
                if run.status not in FINISHED_RUN_STATUSES:
                    self._set_status(tx, run, RunStatus.CANCELLED)
            tx.emit("scan.updated", scan_out(scan), scan.id)
            run_ids = [run.id for run in scan.runs]
        self.gate(scan_id).set()
        for run_id in run_ids:
            if task := self._tasks.get(run_id):
                task.cancel()

    async def retry(self, run_id: int) -> None:
        async with self.bus.transaction() as tx:
            run = await tx.session.get(ModuleRun, run_id)
            if run is None:
                raise not_found("run")
            if run.status != RunStatus.FAILED or not run.retryable:
                raise AppError("run_not_retryable", status=409)
            scan = await self._scan(tx.session, run.scan_id)
            if scan.status == ScanStatus.CANCELLED:
                raise AppError("scan_finished", status=409)
            run.attempts = 0
            run.finished_at = None
            self._set_status(
                tx,
                run,
                RunStatus.PAUSED if scan.status == ScanStatus.PAUSED else RunStatus.QUEUED,
            )
            if scan.status == ScanStatus.DONE:
                scan.status = ScanStatus.RUNNING
                scan.finished_at = None
                tx.emit("scan.updated", scan_out(scan), scan.id)
        self._wake.set()

    # Scheduling

    async def _dispatch_loop(self) -> None:
        while True:
            self._wake.clear()
            try:
                next_wake = await self.db.shielded(self._launch_ready())
            except Exception:
                log.exception("dispatcher failed; trying again")
                next_wake = self.clock.now() + timedelta(seconds=1)
            timeout = None
            if next_wake is not None:
                timeout = max(0.0, self.clock.seconds_until(next_wake)) / self.clock.speed
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout)

    async def _launch_ready(self) -> datetime | None:
        """Starts the runs that may start; returns when to look again for a delayed one."""
        if len(self._tasks) >= self.max_parallel_runs:
            return None
        now = self.clock.now()
        next_wake: datetime | None = None
        launched: list[ModuleRun] = []
        busy = Counter(self._task_modules.values())
        async with self.bus.transaction() as tx:
            runs = await tx.session.scalars(
                select(ModuleRun)
                .join(Scan)
                .where(ModuleRun.status.in_(WAITING), Scan.status == ScanStatus.RUNNING)
                .order_by(ModuleRun.id)
            )
            for run in runs:
                if run.retry_at is not None and run.retry_at > now:
                    next_wake = run.retry_at if next_wake is None else min(next_wake, run.retry_at)
                    continue
                module = self.modules.get(run.module)
                if module is None:
                    run.retryable = True
                    self._finish(tx, run, RunStatus.FAILED, "module_unavailable", {})
                    await self._refresh_scan(tx, await self._scan(tx.session, run.scan_id))
                    continue
                if len(self._tasks) + len(launched) >= self.max_parallel_runs:
                    break
                if busy[run.module] >= module.meta.max_parallel_runs:
                    continue
                busy[run.module] += 1
                if run.status != RunStatus.RATE_LIMITED:
                    run.attempts += 1
                run.started_at = run.started_at or now
                run.retry_at = None
                self._set_status(tx, run, RunStatus.RUNNING)
                launched.append(run)
        for run in launched:
            self._task_modules[run.id] = run.module
            self._tasks[run.id] = asyncio.create_task(self._execute(run), name=f"run-{run.id}")
        return next_wake

    async def _execute(self, run: ModuleRun) -> None:
        module = self.modules[run.module]
        ctx = RunContext(self, run, module.meta)
        target = Target(
            entity_id=run.input_entity.id,
            kind=EntityKind(run.input_entity.kind),
            value=run.input_entity.display,
            normalized=run.input_entity.normalized,
        )
        try:
            async for finding in module.run(ctx, target):
                await ctx.pause_point()
                await self.db.shielded(self._store(run, module.meta, target, finding))
            await self.db.shielded(self._end(run.id, RunStatus.DONE))
        except RateLimited as exc:
            retry_at = self.clock.now() + timedelta(seconds=exc.retry_after)
            await self.db.shielded(
                self._end(run.id, RunStatus.RATE_LIMITED, exc, retry_at=retry_at)
            )
        except TransientError as exc:
            if run.attempts < MAX_ATTEMPTS:
                delay = BACKOFF_SECONDS * 2 ** (run.attempts - 1)
                retry_at = self.clock.now() + timedelta(seconds=delay)
                await self.db.shielded(self._end(run.id, RunStatus.QUEUED, exc, retry_at=retry_at))
            else:
                await self.db.shielded(self._end(run.id, RunStatus.FAILED, exc))
        except ModuleError as exc:
            await self.db.shielded(self._end(run.id, RunStatus.FAILED, exc))
        except asyncio.CancelledError:
            # Cancelled by the user (the run is already marked) or by a shutdown (the run stays
            # "running" and the next start re-queues it).
            raise
        except Exception:
            log.exception("module %s crashed on run %s", run.module, run.id)
            await self.db.shielded(
                self._end(run.id, RunStatus.FAILED, ModuleError("module_crashed"))
            )
        finally:
            self._tasks.pop(run.id, None)
            self._task_modules.pop(run.id, None)
            if not self._stopping:
                self._wake.set()

    async def _store(
        self, run: ModuleRun, meta: ModuleMeta, target: Target, finding: Finding
    ) -> None:
        try:
            display, normalized = normalize(finding.kind, finding.value)
        except AppError:
            log.warning("%s yielded an invalid %s: %r", meta.name, finding.kind, finding.value)
            return
        now = self.clock.now()
        async with self.bus.transaction() as tx:
            current = await tx.session.get(ModuleRun, run.id)
            if current is None or current.status == RunStatus.CANCELLED:
                return
            entity = await upsert_entity(
                tx.session,
                profile_id=run.input_entity.profile_id,
                kind=finding.kind,
                display=display,
                normalized=normalized,
                now=now,
                confidence=finding.confidence,
            )
            edge = await upsert_edge(
                tx.session,
                profile_id=run.input_entity.profile_id,
                source_id=target.entity_id,
                target_id=entity.id,
                relation=finding.relation,
                module=meta.name,
                now=now,
                confidence=finding.confidence,
            )
            duplicate = await tx.session.scalar(
                select(Evidence.id).where(
                    Evidence.run_id == run.id,
                    Evidence.entity_id == entity.id,
                    Evidence.url.is_not_distinct_from(finding.url),
                )
            )
            if duplicate is not None:
                return  # the same finding again, after a restart or a retry
            content_hash = (
                hashlib.sha256(finding.content.encode()).hexdigest() if finding.content else None
            )
            evidence = Evidence(
                entity_id=entity.id,
                edge_id=edge.id,
                scan_id=run.scan_id,
                run_id=run.id,
                module=meta.name,
                url=finding.url,
                excerpt=finding.excerpt,
                content_hash=content_hash,
                captured_at=now,
            )
            tx.session.add(evidence)
            current.results_count += 1
            current.updated_at = now
            await tx.session.execute(
                update(Scan)
                .where(Scan.id == run.scan_id)
                .values(results_count=Scan.results_count + 1)
            )
            await tx.session.flush()
            tx.emit(
                "result.created",
                ResultOut(
                    id=evidence.id,
                    scan_id=run.scan_id,
                    run_id=run.id,
                    module=meta.name,
                    entity=EntityOut.model_validate(entity),
                    relation=finding.relation,
                    confidence=finding.confidence,
                    url=finding.url,
                    excerpt=finding.excerpt,
                    captured_at=now,
                ),
                run.scan_id,
            )

    async def _end(
        self,
        run_id: int,
        status: RunStatus,
        error: ModuleError | None = None,
        *,
        retry_at: datetime | None = None,
    ) -> None:
        async with self.bus.transaction() as tx:
            run = await tx.session.get(ModuleRun, run_id)
            if run is None or run.status in FINISHED_RUN_STATUSES:
                return  # cancelled meanwhile
            run.retry_at = retry_at
            run.retryable = error.retryable if error else False
            if run.status == RunStatus.PAUSED and status in WAITING:
                status = RunStatus.PAUSED  # it will wait for its retry_at once resumed
            if status in FINISHED_RUN_STATUSES:
                self._finish(
                    tx,
                    run,
                    status,
                    error.code if error else None,
                    error.params if error else None,
                )
            else:
                run.error_code = error.code if error else None
                run.error_params = error.params if error else None
                self._set_status(tx, run, status)
            await self._refresh_scan(tx, await self._scan(tx.session, run.scan_id))

    # State changes (always through these, so that each one is an event)

    def _set_status(self, tx: Transaction, run: ModuleRun, status: RunStatus) -> None:
        run.status = status
        run.updated_at = self.clock.now()
        if status == RunStatus.RUNNING or (status == RunStatus.QUEUED and run.retry_at is None):
            run.error_code = None
            run.error_params = None
        tx.emit("run.updated", RunOut.of(run), run.scan_id)

    def _finish(
        self,
        tx: Transaction,
        run: ModuleRun,
        status: RunStatus,
        code: str | None,
        params: dict[str, Any] | None,
    ) -> None:
        run.error_code = code
        run.error_params = params
        run.finished_at = self.clock.now()
        if status == RunStatus.DONE:
            run.progress_done = run.progress_total = run.progress_total or run.progress_done
        self._set_status(tx, run, status)

    def _resumed_status(self, run: ModuleRun) -> RunStatus:
        if run.id in self._tasks:
            return RunStatus.RUNNING
        if run.error_code == "rate_limited" and run.retry_at and run.retry_at > self.clock.now():
            return RunStatus.RATE_LIMITED
        return RunStatus.QUEUED

    async def _refresh_scan(self, tx: Transaction, scan: Scan) -> None:
        """Marks a running scan done once none of its runs is left to do."""
        await tx.session.refresh(scan, ["runs"])
        if scan.status != ScanStatus.RUNNING:
            return
        if all(run.status in FINISHED_RUN_STATUSES for run in scan.runs):
            scan.status = ScanStatus.DONE
            scan.finished_at = self.clock.now()
            tx.emit("scan.updated", scan_out(scan), scan.id)

    async def _scan(self, session: AsyncSession, scan_id: int) -> Scan:
        scan = await session.get(Scan, scan_id)
        if scan is None:
            raise not_found("scan")
        return scan
