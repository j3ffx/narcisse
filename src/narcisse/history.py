"""What changed between two scans of a profile: the traces that appeared, those gone, those a
later scan couldn't vouch for, and those whose page changed.

A trace is gone only if the later scan ran again, without error, every search that had found it
(the same rule as `remediation/follow.py`); a trace whose searches didn't all run again is only
"not checked again".
"""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from narcisse.domain import EntityStatus, RunStatus, ScanStatus
from narcisse.errors import AppError, not_found
from narcisse.storage.models import Entity, Evidence, ModuleRun, Scan


@dataclass(frozen=True)
class Diff:
    before: Scan
    after: Scan
    new: list[Entity]
    gone: list[Entity]
    unchecked: list[Entity]
    modified: list[Entity]


def is_check(scan: Scan) -> bool:
    return bool((scan.notes or {}).get("check"))


async def comparable_scans(session: AsyncSession, profile_id: int) -> list[Scan]:
    """The profile's finished scans worth comparing (not the checks of one trace), oldest first."""
    scans = await session.scalars(
        select(Scan)
        .where(Scan.profile_id == profile_id, Scan.status == ScanStatus.DONE)
        .order_by(Scan.id)
    )
    return [scan for scan in scans if not is_check(scan)]


async def _seen(session: AsyncSession, scan_id: int) -> set[int]:
    return set(await session.scalars(select(Evidence.entity_id).where(Evidence.scan_id == scan_id)))


async def _hashes(session: AsyncSession, scan_id: int) -> dict[tuple[int, str], str | None]:
    """The last content hash each source recorded for each trace in this scan."""
    rows = await session.execute(
        select(Evidence.entity_id, Evidence.module, Evidence.content_hash)
        .where(Evidence.scan_id == scan_id, Evidence.content_hash.is_not(None))
        .order_by(Evidence.captured_at, Evidence.id)
    )
    return {(entity_id, module): digest for entity_id, module, digest in rows}


async def compare(
    session: AsyncSession, profile_id: int, before_id: int | None, after_id: int | None
) -> Diff:
    scans = await comparable_scans(session, profile_id)
    by_id = {scan.id: scan for scan in scans}
    if after_id is None:
        if len(scans) < 2:
            raise AppError("not_enough_scans", status=409)
        after = scans[-1]
    else:
        after = by_id.get(after_id) or _missing()
    if before_id is None:
        earlier = [scan for scan in scans if scan.id < after.id]
        if not earlier:
            raise AppError("not_enough_scans", status=409)
        before = earlier[-1]
    else:
        before = by_id.get(before_id) or _missing()
    if before.id >= after.id:
        raise AppError("scans_out_of_order", status=422)

    seen_before = await _seen(session, before.id)
    seen_after = await _seen(session, after.id)
    seen_earlier = set(
        await session.scalars(
            select(Evidence.entity_id)
            .join(Scan, Evidence.scan_id == Scan.id)
            .where(Scan.profile_id == profile_id, Scan.id < after.id)
        )
    )
    new = seen_after - seen_earlier

    lost = seen_before - seen_after
    searches: defaultdict[int, set[tuple[str, int]]] = defaultdict(set)
    if lost:
        rows = await session.execute(
            select(Evidence.entity_id, ModuleRun.module, ModuleRun.input_entity_id)
            .join(ModuleRun, Evidence.run_id == ModuleRun.id)
            .where(Evidence.entity_id.in_(lost), ModuleRun.scan_id <= after.id)
            .distinct()
        )
        for entity_id, module, input_id in rows:
            searches[entity_id].add((module, input_id))
    done_after = {
        (run.module, run.input_entity_id) for run in after.runs if run.status == RunStatus.DONE
    }
    gone = {e for e in lost if searches[e] and searches[e] <= done_after}
    unchecked = lost - gone

    hashes_before = await _hashes(session, before.id)
    hashes_after = await _hashes(session, after.id)
    modified = {
        entity_id
        for (entity_id, module), digest in hashes_after.items()
        if hashes_before.get((entity_id, module)) not in (None, digest)
    }

    wanted = new | gone | unchecked | modified
    entities = {
        e.id: e
        for e in await session.scalars(select(Entity).where(Entity.id.in_(wanted)))
        if e.status != EntityStatus.FALSE_POSITIVE
    }

    def pick(ids: set[int]) -> list[Entity]:
        found = [entities[i] for i in ids if i in entities]
        return sorted(found, key=lambda e: (-(e.risk or 0), e.display))

    return Diff(
        before=before,
        after=after,
        new=pick(new),
        gone=pick(gone),
        unchecked=pick(unchecked),
        modified=pick(modified),
    )


def _missing() -> Scan:
    raise not_found("scan")
