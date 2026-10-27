"""Following what the user did about their traces: when a request is due for a reminder, whether
a later scan still finds the trace, and how exposed a profile is after each scan.

A scan that runs again a search which once found a trace says something about it: found again,
the trace is still there; not found by a search that went to its end, it is gone, and a request
sent about it is done. A search that failed says nothing. "Relancer et vérifier" starts a scan of
just those searches; any other scan of the profile checks the same way.
"""

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from narcisse.domain import (
    OPEN_REQUEST_STATUSES,
    CheckOutcome,
    EntityKind,
    EntityStatus,
    RequestStatus,
    RunStatus,
)
from narcisse.engine.scoring import risk_level
from narcisse.storage.models import (
    Entity,
    Evidence,
    ExposureSnapshot,
    ModuleRun,
    RemovalRequest,
    Scan,
)

# The GDPR gives a month to answer (art. 12.3): past it, a request is worth a reminder.
REMINDER_AFTER = timedelta(days=30)
LEVELS = ("low", "medium", "high", "critical")


def reminder_at(request: RemovalRequest) -> datetime | None:
    """When a sent request deserves a reminder (a month after it was sent, or reminded), if
    it does."""
    if request.status not in OPEN_REQUEST_STATUSES or request.sent_at is None:
        return None
    if request.check == CheckOutcome.GONE:
        return None
    return max(request.sent_at, request.reminded_at or request.sent_at) + REMINDER_AFTER


def is_due(request: RemovalRequest, now: datetime) -> bool:
    when = reminder_at(request)
    return when is not None and when <= now


async def finders(session: AsyncSession, entity_id: int) -> set[tuple[str, int]]:
    """The searches (module, input) that found this trace."""
    rows = await session.execute(
        select(ModuleRun.module, ModuleRun.input_entity_id)
        .join(Evidence, Evidence.run_id == ModuleRun.id)
        .where(Evidence.entity_id == entity_id)
        .distinct()
    )
    return {(module, input_id) for module, input_id in rows}


async def rechecked(session: AsyncSession, scan: Scan) -> tuple[set[int], set[int]]:
    """What a finished scan says of the profile's traces: those it found, and those it no longer
    finds although every search that once found them ran again without error."""
    done_here = {
        (run.module, run.input_entity_id) for run in scan.runs if run.status == RunStatus.DONE
    }
    found = set(
        await session.scalars(select(Evidence.entity_id).where(Evidence.scan_id == scan.id))
    )
    rows = await session.execute(
        select(Evidence.entity_id, ModuleRun.module, ModuleRun.input_entity_id)
        .join(ModuleRun, Evidence.run_id == ModuleRun.id)
        .join(Entity, Evidence.entity_id == Entity.id)
        .where(Entity.profile_id == scan.profile_id)
        .distinct()
    )
    searches: dict[int, set[tuple[str, int]]] = {}
    for entity_id, module, input_id in rows:
        searches.setdefault(entity_id, set()).add((module, input_id))
    gone = {
        entity_id
        for entity_id, found_by in searches.items()
        if entity_id not in found and found_by <= done_here
    }
    return found, gone


async def mark_gone(
    session: AsyncSession, found: set[int], gone: set[int], now: datetime
) -> list[Entity]:
    """Dates the traces a scan no longer finds, and clears the date of those it finds again;
    returns the traces that changed."""
    changed = []
    for ids, when in ((gone, now), (found, None)):
        for part in _slices(sorted(ids)):
            for entity in await session.scalars(select(Entity).where(Entity.id.in_(part))):
                if (entity.gone_at is None) != (when is None):
                    entity.gone_at = when
                    changed.append(entity)
    return changed


async def check_requests(
    session: AsyncSession, scan: Scan, found: set[int], gone: set[int], now: datetime
) -> list[RemovalRequest]:
    """What a finished scan says about the traces the user acts on; returns the requests it
    changed."""
    requests = list(
        await session.scalars(
            select(RemovalRequest).where(
                RemovalRequest.profile_id == scan.profile_id,
                RemovalRequest.status != RequestStatus.REFUSED,
                RemovalRequest.entity_id.in_(found | gone),
            )
        )
    )
    changed = []
    for request in requests:
        outcome = CheckOutcome.GONE if request.entity_id in gone else CheckOutcome.STILL_THERE
        request.check = outcome
        request.checked_at = now
        request.check_scan_id = scan.id
        if outcome == CheckOutcome.GONE and request.status in (
            *OPEN_REQUEST_STATUSES,
            RequestStatus.TODO,
        ):
            request.status = RequestStatus.DONE
            request.closed_at = now
        request.updated_at = now
        changed.append(request)
    return changed


SLICE = 900  # SQLite caps the number of bound parameters


def _slices(items: list[int]) -> list[list[int]]:
    return [items[i : i + SLICE] for i in range(0, len(items), SLICE)]


async def exposure(session: AsyncSession, profile_id: int) -> tuple[dict[str, int], float]:
    """How many of the profile's traces stand at each risk level, and the sum of their risks:
    the user's own (or not rejected), still found in public, not the identity."""
    rows = await session.execute(
        select(Entity.risk).where(
            Entity.profile_id == profile_id,
            Entity.kind != EntityKind.IDENTITY,
            Entity.status != EntityStatus.FALSE_POSITIVE,
            Entity.gone_at.is_(None),
            Entity.risk > 0,
        )
    )
    counts: Counter[str] = Counter()
    total = 0.0
    for (risk,) in rows:
        if risk is None:
            continue
        counts[risk_level(risk)] += 1
        total += risk
    return {level: counts[level] for level in LEVELS}, round(total, 2)


async def snapshot(session: AsyncSession, scan: Scan, now: datetime) -> ExposureSnapshot:
    levels, total = await exposure(session, scan.profile_id)
    shot = ExposureSnapshot(
        profile_id=scan.profile_id, scan_id=scan.id, taken_at=now, levels=levels, exposure=total
    )
    session.add(shot)
    return shot
