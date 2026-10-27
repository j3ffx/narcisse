"""The actions the user follows on their traces (a request sent, an account to delete…): their
status, the reminder a month after sending, the check that the trace is gone, and the profile's
exposure over time."""

from datetime import datetime

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from narcisse.api.deps import ServicesDep
from narcisse.api.remediation import request_out, trace_context
from narcisse.domain import OPEN_REQUEST_STATUSES, CheckOutcome, RequestStatus
from narcisse.engine.events import Transaction
from narcisse.errors import AppError, not_found
from narcisse.remediation import follow, letters
from narcisse.schemas import (
    DueOut,
    ExposureOut,
    ExposurePoint,
    LetterOut,
    RequestIn,
    RequestOut,
    RequestPatch,
    ScanDetail,
)
from narcisse.storage.models import ExposureSnapshot, Profile, RemovalRequest

router = APIRouter(tags=["requests"])

CLOSED = (RequestStatus.DONE, RequestStatus.REFUSED)


def _emit(tx: Transaction, profile_id: int) -> None:
    tx.emit("requests.updated", {"profile_id": profile_id}, None)


def _status(request: RemovalRequest, status: RequestStatus, now: datetime) -> None:
    request.status = status
    if status in OPEN_REQUEST_STATUSES and request.sent_at is None:
        request.sent_at = now
    request.closed_at = now if status in CLOSED else None


@router.get("/profiles/{profile_id}/requests")
async def list_requests(profile_id: int, s: ServicesDep) -> list[RequestOut]:
    now = s.engine.clock.now()
    async with s.db.snapshot() as session:
        if await session.get(Profile, profile_id) is None:
            raise not_found("profile")
        requests = await session.scalars(
            select(RemovalRequest)
            .where(RemovalRequest.profile_id == profile_id)
            .order_by(RemovalRequest.updated_at.desc(), RemovalRequest.id.desc())
        )
        return [request_out(r, now) for r in requests]


@router.post("/entities/{entity_id}/requests", status_code=201)
async def follow_action(entity_id: int, body: RequestIn, s: ServicesDep) -> RequestOut:
    """Starts following an action of the trace's sheet, or updates the one already followed
    (the same action on the same site)."""
    now = s.engine.clock.now()
    async with s.bus.transaction() as tx:
        trace = await trace_context(tx.session, entity_id)
        request = await tx.session.scalar(
            select(RemovalRequest).where(
                RemovalRequest.entity_id == entity_id,
                RemovalRequest.action == body.action,
                RemovalRequest.service == body.service,
            )
        )
        if request is None:
            request = RemovalRequest(
                profile_id=trace.entity.profile_id,
                entity_id=entity_id,
                action=body.action,
                service=body.service,
                created_at=now,
                sent_at=None,
                closed_at=None,
            )
            tx.session.add(request)
        for key in ("letter", "recipient", "subject", "body"):
            value = getattr(body, key)
            if value is not None:
                setattr(request, key, value)
        _status(request, body.status, now)
        request.updated_at = now
        try:
            await tx.session.flush()
        except IntegrityError as exc:  # the same action followed twice at once
            raise AppError("request_exists", status=409) from exc
        await tx.session.refresh(request, ["entity"])
        out = request_out(request, now)
        _emit(tx, request.profile_id)
    return out


@router.patch("/requests/{request_id}")
async def update_request(request_id: int, body: RequestPatch, s: ServicesDep) -> RequestOut:
    now = s.engine.clock.now()
    async with s.bus.transaction() as tx:
        request = await tx.session.get(RemovalRequest, request_id)
        if request is None:
            raise not_found("request")
        if body.status is not None:
            _status(request, body.status, now)
        if body.recipient is not None:
            request.recipient = body.recipient.strip() or None
        if body.note is not None:
            request.note = body.note.strip() or None
        if body.reminded:
            request.reminded_at = now
        request.updated_at = now
        out = request_out(request, now)
        _emit(tx, request.profile_id)
    return out


@router.delete("/requests/{request_id}", status_code=204)
async def stop_following(request_id: int, s: ServicesDep) -> Response:
    async with s.bus.transaction() as tx:
        request = await tx.session.get(RemovalRequest, request_id)
        if request is None:
            raise not_found("request")
        await tx.session.delete(request)
        _emit(tx, request.profile_id)
    return Response(status_code=204)


@router.get("/requests/{request_id}/reminder")
async def get_reminder(request_id: int, s: ServicesDep) -> dict[str, LetterOut]:
    """The reminder of a sent request, in French and in English, the request copied below."""
    today = s.engine.clock.now().date()
    async with s.db.snapshot() as session:
        request = await session.get(RemovalRequest, request_id)
        if request is None:
            raise not_found("request")
        if request.sent_at is None:
            raise AppError("request_not_sent", status=409)
        trace = await trace_context(session, request.entity_id)
    context = trace.letter_context(request.service or None, today)
    out = {}
    for lang in ("fr", "en"):
        letter = letters.reminder(
            lang,
            context,
            sent=request.sent_at.date(),
            subject=request.subject,
            body=request.body,
        )
        out[lang] = LetterOut(subject=letter.subject, body=letter.body)
    return out


@router.post("/requests/{request_id}/check", status_code=201)
async def check_request(request_id: int, s: ServicesDep) -> ScanDetail:
    """Runs again the searches that found the trace; their end says whether it is gone."""
    return await s.engine.start_check(request_id)


@router.get("/profiles/{profile_id}/exposure")
async def get_exposure(profile_id: int, s: ServicesDep) -> ExposureOut:
    now = s.engine.clock.now()
    async with s.db.snapshot() as session:
        if await session.get(Profile, profile_id) is None:
            raise not_found("profile")
        levels, total = await follow.exposure(session, profile_id)
        history = await session.scalars(
            select(ExposureSnapshot)
            .where(ExposureSnapshot.profile_id == profile_id)
            .order_by(ExposureSnapshot.taken_at, ExposureSnapshot.id)
        )
        requests = list(
            await session.scalars(
                select(RemovalRequest).where(RemovalRequest.profile_id == profile_id)
            )
        )
        by_status = {status.value: 0 for status in RequestStatus}
        for request in requests:
            by_status[request.status] += 1
        return ExposureOut(
            levels=levels,
            exposure=total,
            history=[
                ExposurePoint(
                    taken_at=shot.taken_at,
                    scan_id=shot.scan_id,
                    levels=shot.levels,
                    exposure=shot.exposure,
                )
                for shot in history
            ],
            requests=by_status,
            due=sum(follow.is_due(r, now) for r in requests),
            gone=sum(r.check == CheckOutcome.GONE for r in requests),
        )


@router.get("/requests/due")
async def due_requests(s: ServicesDep) -> DueOut:
    """How many sent requests, all profiles together, wait for a reminder."""
    now = s.engine.clock.now()
    async with s.db.snapshot() as session:
        sent = await session.scalars(
            select(RemovalRequest).where(RemovalRequest.status.in_(OPEN_REQUEST_STATUSES))
        )
        return DueOut(count=sum(follow.is_due(r, now) for r in sent))
