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


async def check_requests(session: AsyncSession, scan: Scan, now: datetime) -> list[RemovalRequest]:
    """What this finished scan says about the traces the user acts on; returns the requests it
    changed."""
    requests = list(
        await session.scalars(
            select(RemovalRequest).where(
                RemovalRequest.profile_id == scan.profile_id,
                RemovalRequest.status != RequestStatus.REFUSED,
            )
        )
    )
    if not requests:
        return []
    done_here = {
        (run.module, run.input_entity_id) for run in scan.runs if run.status == RunStatus.DONE
    }
    changed = []
    for request in requests:
        looked = await finders(session, request.entity_id) & done_here
        if not looked:
            continue  # this scan didn't run any search that found it
        found_again = await session.scalar(
            select(Evidence.id)
            .where(Evidence.entity_id == request.entity_id, Evidence.scan_id == scan.id)
            .limit(1)
        )
        outcome = CheckOutcome.STILL_THERE if found_again else CheckOutcome.GONE
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


async def gone_entities(session: AsyncSession, profile_id: int) -> set[int]:
    """Traces a scan no longer found after the user acted on them."""
    return set(
        await session.scalars(
            select(RemovalRequest.entity_id).where(
                RemovalRequest.profile_id == profile_id,
                RemovalRequest.check == CheckOutcome.GONE,
            )
        )
    )


async def exposure(session: AsyncSession, profile_id: int) -> tuple[dict[str, int], float]:
    """How many of the profile's traces stand at each risk level, and the sum of their risks:
    the user's own (or not rejected), still public, not the identity."""
    gone = await gone_entities(session, profile_id)
    rows = await session.execute(
        select(Entity.id, Entity.risk).where(
            Entity.profile_id == profile_id,
            Entity.kind != EntityKind.IDENTITY,
            Entity.status != EntityStatus.FALSE_POSITIVE,
            Entity.risk > 0,
        )
    )
    counts: Counter[str] = Counter()
    total = 0.0
    for entity_id, risk in rows:
        if entity_id in gone or risk is None:
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
