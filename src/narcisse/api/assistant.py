"""The optional assistant: its state, the questions the user asks it about traces, and what the
user does with its answers (apply a verdict, rewrite or hide an explanation)."""

from fastapi import APIRouter, Response
from sqlalchemy import select

from narcisse.api.deps import ServicesDep
from narcisse.api.entities import review
from narcisse.domain import EntityStatus
from narcisse.errors import AppError, not_found
from narcisse.llm.assistant import emit
from narcisse.llm.provider import LLMError, validated
from narcisse.llm.tasks import TASKS
from narcisse.schemas import (
    AnnotationIn,
    AnnotationOut,
    AnnotationPatch,
    AnnotationTask,
    AssistantOut,
    PromptOut,
    TriageOut,
    TryOut,
)
from narcisse.storage.models import Annotation, Entity, Profile

router = APIRouter(tags=["assistant"])

VERDICTS = {"me": EntityStatus.CONFIRMED, "not_me": EntityStatus.FALSE_POSITIVE}


@router.get("/assistant")
async def assistant_status(s: ServicesDep) -> AssistantOut:
    return await s.assistant.status()


@router.post("/assistant/try")
async def try_assistant(s: ServicesDep) -> TryOut:
    return await s.assistant.try_it()


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
