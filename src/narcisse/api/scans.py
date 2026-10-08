"""Scans, their runs and results, the activity centre, and the live event stream."""

from collections.abc import AsyncIterable
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityKind, ScanStatus
from narcisse.engine.engine import scan_detail, scan_out
from narcisse.errors import not_found
from narcisse.schemas import (
    ActivityOut,
    EntityOut,
    ModuleOut,
    ResultOut,
    ResultsPage,
    ScanDetail,
    ScanOut,
)
from narcisse.storage.models import Edge, Entity, Event, Evidence, Profile, Scan

router = APIRouter(tags=["scans"])

# Finished scans stay in the activity centre that long.
RECENT = timedelta(hours=24)
RECENT_LIMIT = 20


class ScanIn(BaseModel):
    # Empty: the profile's default modules, or every module.
    modules: list[str] = []


@router.get("/modules")
async def list_modules(s: ServicesDep) -> list[ModuleOut]:
    return [
        ModuleOut.model_validate(
            {
                **vars(m.meta),
                "accepts": sorted(m.meta.accepts),
                "produces": sorted(m.meta.produces),
                "hosts": list(m.meta.hosts),
                "rate_limit": vars(m.meta.rate_limit) if m.meta.rate_limit else None,
            }
        )
        for m in sorted(s.engine.modules.values(), key=lambda m: (m.meta.category, m.meta.name))
    ]


@router.get("/profiles/{profile_id}/scans")
async def list_scans(profile_id: int, s: ServicesDep) -> list[ScanOut]:
    async with s.db.read() as session:
        if await session.get(Profile, profile_id) is None:
            raise not_found("profile")
        scans = await session.scalars(
            select(Scan).where(Scan.profile_id == profile_id).order_by(Scan.id.desc())
        )
        return [scan_out(scan) for scan in scans]


@router.post("/profiles/{profile_id}/scans", status_code=201)
async def start_scan(profile_id: int, body: ScanIn, s: ServicesDep) -> ScanDetail:
    return await s.engine.start_scan(profile_id, body.modules or None)


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: int, s: ServicesDep) -> ScanDetail:
    async with s.db.read() as session:
        scan = await session.get(Scan, scan_id)
        if scan is None:
            raise not_found("scan")
        return scan_detail(scan)


@router.post("/scans/{scan_id}/pause", status_code=204)
async def pause_scan(scan_id: int, s: ServicesDep) -> Response:
    await s.engine.pause(scan_id)
    return Response(status_code=204)


@router.post("/scans/{scan_id}/resume", status_code=204)
async def resume_scan(scan_id: int, s: ServicesDep) -> Response:
    await s.engine.resume(scan_id)
    return Response(status_code=204)


@router.post("/scans/{scan_id}/cancel", status_code=204)
async def cancel_scan(scan_id: int, s: ServicesDep) -> Response:
    await s.engine.cancel(scan_id)
    return Response(status_code=204)


@router.post("/runs/{run_id}/retry", status_code=204)
async def retry_run(run_id: int, s: ServicesDep) -> Response:
    await s.engine.retry(run_id)
    return Response(status_code=204)


@router.get("/scans/{scan_id}/results")
async def list_results(
    scan_id: int,
    s: ServicesDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    kind: EntityKind | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> ResultsPage:
    query = (
        select(Evidence, Entity, Edge.relation, Edge.confidence)
        .join(Entity, Evidence.entity_id == Entity.id)
        .outerjoin(Edge, Evidence.edge_id == Edge.id)
        .where(Evidence.scan_id == scan_id)
    )
    if kind is not None:
        query = query.where(Entity.kind == kind)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Entity.display.ilike(pattern), Evidence.url.ilike(pattern)))
    async with s.db.read() as session:
        total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = await session.execute(query.order_by(Evidence.id).offset(offset).limit(limit))
        items = [
            ResultOut(
                id=evidence.id,
                scan_id=evidence.scan_id,
                run_id=evidence.run_id,
                module=evidence.module,
                entity=EntityOut.model_validate(entity),
                relation=relation,
                confidence=confidence,
                url=evidence.url,
                excerpt=evidence.excerpt,
                captured_at=evidence.captured_at,
            )
            for evidence, entity, relation, confidence in rows
        ]
    return ResultsPage(items=items, total=total)


@router.get("/activity")
async def activity(s: ServicesDep) -> ActivityOut:
    """What runs and what just ran, with the id of the last event it includes."""
    since = s.bus.clock.now() - RECENT
    async with s.db.snapshot() as session:
        last_event_id = await session.scalar(select(func.max(Event.id))) or 0
        scans = await session.scalars(
            select(Scan)
            .where(
                or_(
                    Scan.status.in_((ScanStatus.RUNNING, ScanStatus.PAUSED)),
                    Scan.finished_at >= since,
                )
            )
            .order_by(Scan.id.desc())
            .limit(RECENT_LIMIT)
        )
        return ActivityOut(last_event_id=last_event_id, scans=[scan_detail(x) for x in scans])


@router.get("/events", response_class=EventSourceResponse)
async def events(
    s: ServicesDep,
    after: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[str | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    """Every event after `after` (or after the browser's `Last-Event-ID` when it reconnects),
    then the new ones as they happen. A `reset` event means "reload everything": the events the
    client missed are gone (pruned, or another data directory)."""
    cursor = int(last_event_id) if last_event_id and last_event_id.isdigit() else after
    oldest = await s.bus.oldest_id()
    pruned = oldest is not None and cursor < oldest - 1
    if cursor > s.bus.latest_id or (pruned and cursor > 0):
        cursor = s.bus.latest_id
        yield ServerSentEvent(event="reset", data={}, id=str(cursor), retry=1000)
    else:
        yield ServerSentEvent(comment="connected", retry=1000)
    while True:
        batch = await s.bus.read_after(cursor)
        for event in batch:
            cursor = event.id
            yield ServerSentEvent(id=str(event.id), event=event.type, data=event.payload)
        # FastAPI sends keep-alive comments while this waits.
        if not batch and not await s.bus.wait_after(cursor):
            return  # shutting down
