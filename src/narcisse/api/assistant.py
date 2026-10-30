"""The optional assistant: its state, the questions the user asks it about traces, and what the
user does with its answers (apply a verdict, rewrite or hide an explanation)."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from functools import cache

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from narcisse.api.deps import ServicesDep
from narcisse.api.entities import review
from narcisse.domain import EntityKind, EntityStatus
from narcisse.errors import AppError, not_found
from narcisse.llm import local, machine
from narcisse.llm.assistant import emit
from narcisse.llm.provider import LLMError, validated
from narcisse.llm.tasks import TASKS, letter_prompt
from narcisse.normalize import normalize
from narcisse.schemas import (
    AiLeadOut,
    AnnotationIn,
    AnnotationOut,
    AnnotationPatch,
    AnnotationTask,
    AssistantOut,
    EntityOut,
    LetterIn,
    MachineOut,
    PromptOut,
    PullIn,
    PullOut,
    TriageOut,
    TryOut,
)
from narcisse.storage.models import Annotation, Entity, Profile, Seed

router = APIRouter(tags=["assistant"])

VERDICTS = {"me": EntityStatus.CONFIRMED, "not_me": EntityStatus.FALSE_POSITIVE}


@router.get("/assistant")
async def assistant_status(s: ServicesDep) -> AssistantOut:
    return await s.assistant.status()


@router.post("/assistant/try")
async def try_assistant(s: ServicesDep) -> TryOut:
    return await s.assistant.try_it()


@cache
def _machine() -> machine.Machine:
    """Read once: a machine's memory and cards don't change while Narcisse runs."""
    return machine.detect()


@router.get("/assistant/machine")
async def machine_resources(s: ServicesDep) -> MachineOut:
    """What this machine can run, the model that suits it, and the model servers running."""
    found, servers = await asyncio.gather(
        asyncio.to_thread(_machine), local.probe(s.assistant.client)
    )
    return MachineOut.model_validate(
        {
            **asdict(found),
            "recommended": asdict(machine.recommend(found)),
            "servers": [asdict(server) for server in servers],
        }
    )


def _pull_out(s: ServicesDep) -> PullOut:
    return PullOut.model_validate(asdict(s.pull.state))


@router.get("/assistant/pull")
async def pull_state(s: ServicesDep) -> PullOut:
    return _pull_out(s)


@router.post("/assistant/pull", status_code=202)
async def pull_model(body: PullIn, s: ServicesDep) -> PullOut:
    """Has Ollama download a model (the user confirmed its size)."""
    if s.settings.demo:
        raise AppError("llm_provider_unavailable", status=409)
    s.pull.start(body.model)
    return _pull_out(s)


@router.delete("/assistant/pull")
async def cancel_pull(s: ServicesDep) -> PullOut:
    await s.pull.cancel()
    return _pull_out(s)


@router.get("/entities/{entity_id}/annotations")
async def list_annotations(entity_id: int, s: ServicesDep) -> list[AnnotationOut]:
    """What the assistant said about a trace, the latest first."""
    async with s.db.read() as session:
        if await session.get(Entity, entity_id) is None:
            raise not_found("entity")
        rows = await session.scalars(
            select(Annotation)
            .where(Annotation.entity_id == entity_id)
            .order_by(Annotation.id.desc())
        )
        return [AnnotationOut.model_validate(a) for a in rows]


@router.get("/entities/{entity_id}/prompt")
async def preview_prompt(entity_id: int, task: AnnotationTask, s: ServicesDep) -> PromptOut:
    """What asking about this trace would send, before the user sends it."""
    return PromptOut(text=await s.assistant.preview(entity_id, task))


@router.post("/entities/{entity_id}/annotations", status_code=202)
async def ask_assistant(entity_id: int, body: AnnotationIn, s: ServicesDep) -> AnnotationOut:
    return (await s.assistant.ask([entity_id], body.task))[0]


def _letter_text(body: LetterIn) -> Callable[[AsyncSession, Entity], Awaitable[str]]:
    return lambda session, entity: letter_prompt(
        session, entity, body.subject, body.body, body.context, body.tone
    )


@router.post("/entities/{entity_id}/letter/prompt")
async def preview_letter(entity_id: int, body: LetterIn, s: ServicesDep) -> PromptOut:
    """What adapting this letter would send: the profile's identity behind markers."""
    async with s.db.snapshot() as session:
        entity = await session.get(Entity, entity_id)
        if entity is None:
            raise not_found("entity")
        return PromptOut(text=await _letter_text(body)(session, entity))


@router.post("/entities/{entity_id}/letter", status_code=202)
async def adapt_letter(entity_id: int, body: LetterIn, s: ServicesDep) -> AnnotationOut:
    return (await s.assistant.ask([entity_id], "letter", _letter_text(body)))[0]


@router.get("/profiles/{profile_id}/ai-leads")
async def ai_leads(profile_id: int, s: ServicesDep) -> list[AiLeadOut]:
    """The elements the assistant read in the traces' proofs that the user neither added nor
    dismissed. They are not traces: the pivot never follows them."""
    await _profile_exists(s, profile_id)
    async with s.db.snapshot() as session:
        seeds = {
            (kind, normalized)
            for kind, normalized in await session.execute(
                select(Seed.kind, Seed.normalized).where(Seed.profile_id == profile_id)
            )
        }
        rows = await session.execute(
            select(Annotation, Entity)
            .join(Entity, Annotation.entity_id == Entity.id)
            .where(
                Annotation.profile_id == profile_id,
                Annotation.task == "leads",
                Annotation.state == "done",
                Annotation.decision != "dismissed",
            )
            .order_by(Annotation.id.desc())
        )
        out: list[AiLeadOut] = []
        seen: set[tuple[str, str]] = set()
        for annotation, source in rows:
            for index, lead in enumerate((annotation.output or {}).get("leads", [])):
                if lead.get("dismissed"):
                    continue
                try:
                    _, normalized = normalize(EntityKind(lead["kind"]), lead["value"])
                except (AppError, KeyError, ValueError):
                    continue
                key = (lead["kind"], normalized)
                if key in seeds or key in seen:
                    continue
                seen.add(key)
                out.append(
                    AiLeadOut(
                        annotation_id=annotation.id,
                        index=index,
                        source=EntityOut.model_validate(source),
                        kind=lead["kind"],
                        value=lead["value"],
                        reason=lead.get("reason", ""),
                    )
                )
        return out


@router.post("/annotations/{annotation_id}/leads/{index}/dismiss")
async def dismiss_ai_lead(annotation_id: int, index: int, s: ServicesDep) -> AnnotationOut:
    async with s.bus.transaction() as tx:
        annotation = await tx.session.get(Annotation, annotation_id)
        leads = (annotation.output or {}).get("leads", []) if annotation else []
        if annotation is None or annotation.task != "leads" or not 0 <= index < len(leads):
            raise not_found("lead")
        leads = [dict(lead) for lead in leads]
        leads[index]["dismissed"] = True
        annotation.output = {**(annotation.output or {}), "leads": leads}
        await tx.session.flush()
        emit(tx, annotation)
        return AnnotationOut.model_validate(annotation)


async def _profile_exists(s: ServicesDep, profile_id: int) -> None:
    async with s.db.read() as session:
        if await session.get(Profile, profile_id) is None:
            raise not_found("profile")


@router.get("/profiles/{profile_id}/triage")
async def triage_preview(profile_id: int, s: ServicesDep) -> TriageOut:
    """How many traces a batch of "is it me?" questions would ask about."""
    await _profile_exists(s, profile_id)
    ids, capped = await s.assistant.triage_candidates(profile_id)
    return TriageOut(count=len(ids), capped=capped)


@router.post("/profiles/{profile_id}/triage", status_code=202)
async def triage(profile_id: int, s: ServicesDep) -> TriageOut:
    await _profile_exists(s, profile_id)
    ids, capped = await s.assistant.triage_candidates(profile_id)
    if ids:
        await s.assistant.ask(ids, "triage")
    return TriageOut(count=len(ids), capped=capped)


@router.patch("/annotations/{annotation_id}")
async def update_annotation(
    annotation_id: int, body: AnnotationPatch, s: ServicesDep
) -> AnnotationOut:
    async with s.bus.transaction() as tx:
        annotation = await tx.session.get(Annotation, annotation_id)
        if annotation is None:
            raise not_found("annotation")
        if annotation.state != "done":
            raise AppError("annotation_not_ready", status=409)
        if body.output is not None:
            if annotation.task != "explain":
                raise AppError("annotation_not_editable", status=409)
            try:
                annotation.output = validated(TASKS[annotation.task], body.output)
            except LLMError as exc:
                fields = {"fields": ["output"]}
                raise AppError("invalid_request", status=422, params=fields) from exc
            annotation.edited = True
        if body.decision is not None:
            if body.decision == "accepted" and annotation.task == "triage":
                status = VERDICTS.get((annotation.output or {}).get("verdict", ""))
                if status is None:
                    raise AppError("annotation_not_applicable", status=409)
                entity = await tx.session.get(Entity, annotation.entity_id)
                if entity is None:
                    raise not_found("entity")
                await review(tx, entity, status)
            annotation.decision = body.decision
        await tx.session.flush()
        emit(tx, annotation)
        return AnnotationOut.model_validate(annotation)


@router.delete("/annotations/{annotation_id}", status_code=204)
async def delete_annotation(annotation_id: int, s: ServicesDep) -> Response:
    async with s.bus.transaction() as tx:
        annotation = await tx.session.get(Annotation, annotation_id)
        if annotation is None:
            raise not_found("annotation")
        profile_id, entity_id = annotation.profile_id, annotation.entity_id
        await tx.session.delete(annotation)
        tx.emit(
            "annotation.deleted",
            {"id": annotation_id, "entity_id": entity_id, "profile_id": profile_id},
            None,
        )
    return Response(status_code=204)
