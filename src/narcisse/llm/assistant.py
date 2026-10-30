"""The assistant's queue: questions the user asks about traces, answered one at a time.

A question is stored before it is sent (with the exact text that will be sent), so the UI shows it
waiting, and a restart picks up where it stopped. Answers only ever become annotations; nothing
here touches a trace.
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable

from sqlalchemy import select, update

from narcisse.domain import EntityKind, EntityStatus
from narcisse.engine.events import EventBus, Transaction
from narcisse.errors import AppError, not_found
from narcisse.llm import claude_code
from narcisse.llm.claude_code import ClaudeCode
from narcisse.llm.demo import Demo
from narcisse.llm.provider import LLMError, Provider, Status
from narcisse.llm.tasks import TASKS, TRY, prompt
from narcisse.preferences import Preferences
from narcisse.schemas import AnnotationOut, AssistantOut, TryOut
from narcisse.storage.models import Annotation, Entity

log = logging.getLogger(__name__)

# One batch of "is it me?" questions; the user can ask for the next one.
MAX_BATCH = 50
# How long a provider's status is trusted (asking it starts a process).
STATUS_TTL = 30.0

Factory = Callable[[Preferences], Provider | None]


def emit(tx: Transaction, annotation: Annotation) -> None:
    out = AnnotationOut.model_validate(annotation).model_dump(mode="json")
    tx.emit("annotation.updated", {**out, "profile_id": annotation.profile_id}, None)


class Assistant:
    def __init__(
        self,
        bus: EventBus,
        preferences: Callable[[], Preferences],
        *,
        demo: bool,
        factory: Factory | None = None,
    ) -> None:
        self.bus = bus
        self._preferences = preferences
        self.demo = demo
        self._factory = factory or self._provider_for
        self._wake = asyncio.Event()
        self._worker: asyncio.Task[None] | None = None
        self._status: tuple[float, tuple[str, str | None], Status] | None = None

    # Which provider

    def providers(self) -> list[str]:
        """Demo mode offers the demo assistant only, as it offers the demo source only."""
        return ["none", "demo"] if self.demo else ["none", "claude_code"]

    def _provider_for(self, preferences: Preferences) -> Provider | None:
        if preferences.llm_provider == "demo":
            return Demo(self.bus.clock)
        if preferences.llm_provider == "claude_code":
            return ClaudeCode(preferences.llm_model)
        return None

    def provider(self) -> Provider | None:
        preferences = self._preferences()
        if preferences.llm_provider not in self.providers():
            return None
        return self._factory(preferences)

    def forget(self) -> None:
        """The settings changed: ask the provider again."""
        self._status = None

    async def status(self) -> AssistantOut:
        preferences = self._preferences()
        provider = self.provider()
        if provider is None:
            return AssistantOut(
                provider="none",
                providers=self.providers(),
                model=None,
                models=[],
                remote=False,
                remote_ok=preferences.llm_remote_ok,
                available=False,
                reason="llm_off",
            )
        key = (provider.name, provider.model)
        cached = self._status
        if cached is not None and cached[1] == key and time.monotonic() - cached[0] < STATUS_TTL:
            status = cached[2]
        else:
            status = await provider.status()
            self._status = (time.monotonic(), key, status)
        return AssistantOut(
            provider=provider.name,
            providers=self.providers(),
            model=provider.model,
            models=list(claude_code.MODELS) if provider.name == "claude_code" else [],
            remote=provider.remote,
            remote_ok=preferences.llm_remote_ok,
            available=status.available,
            reason=status.reason,
        )

    def usable(self) -> Provider:
        """The chosen provider, if the user may send it something now."""
        provider = self.provider()
        if provider is None:
            raise AppError("llm_off", status=409)
        if provider.remote and not self._preferences().llm_remote_ok:
            raise AppError("llm_remote_consent", status=409)
        return provider

    # Questions

    async def preview(self, entity_id: int, task: str) -> str:
        async with self.bus.db.snapshot() as session:
            entity = await session.get(Entity, entity_id)
            if entity is None:
                raise not_found("entity")
            return await prompt(session, TASKS[task], entity)

    async def ask(self, entity_ids: list[int], task: str) -> list[AnnotationOut]:
        """Queues one question per trace; the answers arrive as `annotation.updated` events."""
        provider = self.usable()
        now = self.bus.clock.now()
        created = []
        async with self.bus.transaction() as tx:
            for entity_id in entity_ids:
                entity = await tx.session.get(Entity, entity_id)
                if entity is None:
                    raise not_found("entity")
                if entity.kind == EntityKind.IDENTITY:
                    raise AppError("entity_not_reviewable", status=409)
                annotation = Annotation(
                    profile_id=entity.profile_id,
                    entity_id=entity.id,
                    task=task,
                    provider=provider.name,
                    model=provider.model,
                    prompt=await prompt(tx.session, TASKS[task], entity),
                    output=None,
                    edited=False,
                    state="queued",
                    decision="pending",
                    created_at=now,
                )
                tx.session.add(annotation)
                await tx.session.flush()
                emit(tx, annotation)
                created.append(AnnotationOut.model_validate(annotation))
        self._wake.set()
        return created

    async def triage_candidates(self, profile_id: int) -> tuple[list[int], bool]:
        """The traces still waiting for a review that were never asked about, the most exposing
        first: one batch of them, and whether more are waiting."""
        async with self.bus.db.snapshot() as session:
            asked = select(Annotation.entity_id).where(Annotation.task == "triage")
            ids = list(
                await session.scalars(
                    select(Entity.id)
                    .where(
                        Entity.profile_id == profile_id,
                        Entity.status == EntityStatus.UNREVIEWED,
                        Entity.kind != EntityKind.IDENTITY,
                        Entity.gone_at.is_(None),
                        Entity.id.not_in(asked),
                    )
                    .order_by(Entity.risk.desc().nulls_last(), Entity.id)
                    .limit(MAX_BATCH + 1)
                )
            )
        return ids[:MAX_BATCH], len(ids) > MAX_BATCH

    async def try_it(self) -> TryOut:
        """A neutral question (no data), to see the provider answers."""
        provider = self.usable()
        try:
            reply = await provider.ask(TRY, "Réponds ok.")
        except LLMError as exc:
            raise AppError(exc.code, status=502, params=exc.params) from exc
        self.forget()
        return TryOut(model=reply.model)

    # The queue

    async def start(self) -> None:
        # A question cut short by a stop is asked again.
        async with self.bus.db.write() as session:
            await session.execute(
                update(Annotation).where(Annotation.state == "running").values(state="queued")
            )
        self._worker = asyncio.create_task(self._work(), name="assistant")
        self._wake.set()

    async def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker
            self._worker = None

    async def _work(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while (job := await self.bus.db.shielded(self._next())) is not None:
                await self._answer(*job)

    async def _next(self) -> tuple[int, str, str] | None:
        async with self.bus.transaction() as tx:
            annotation = await tx.session.scalar(
                select(Annotation).where(Annotation.state == "queued").order_by(Annotation.id)
            )
            if annotation is None:
                return None
            annotation.state = "running"
            await tx.session.flush()
            emit(tx, annotation)
            return annotation.id, annotation.task, annotation.prompt

    async def _answer(self, annotation_id: int, task: str, text: str) -> None:
        output = model = code = None
        params: dict[str, object] | None = None
        provider = self.provider()
        try:
            if provider is None:
                raise LLMError("llm_off")
            reply = await provider.ask(TASKS[task], text)
            output, model = reply.data, reply.model
        except LLMError as exc:
            code, params = exc.code, exc.params or None
        except Exception:
            log.exception("the assistant failed on annotation %s", annotation_id)
            code = "llm_failed"
        await self.bus.db.shielded(self._store(annotation_id, output, model, code, params))

    async def _store(
        self,
        annotation_id: int,
        output: dict[str, object] | None,
        model: str | None,
        code: str | None,
        params: dict[str, object] | None,
    ) -> None:
        async with self.bus.transaction() as tx:
            annotation = await tx.session.get(Annotation, annotation_id)
            if annotation is None:  # deleted while it was being answered
                return
            annotation.state = "failed" if code else "done"
            annotation.output = output
            annotation.model = model or annotation.model
            annotation.error_code = code
            annotation.error_params = params
            annotation.finished_at = self.bus.clock.now()
            await tx.session.flush()
            emit(tx, annotation)
