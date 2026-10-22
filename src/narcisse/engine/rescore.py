"""Keeps the stored scores of traces up to date (the rules live in `scoring.py`).

A trace's scores depend on its links and on the traces at their other end (one the user confirms
or rejects changes its neighbours' confidence), so the callers pass the traces something
happened to, and their neighbours when a status changed.
"""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from narcisse.domain import EntityKind, EntityStatus
from narcisse.engine.scoring import Link, Neighbour, Trace, score
from narcisse.storage.models import Edge, Entity, Evidence

# SQLite caps the number of bound parameters: ask in slices.
SLICE = 900
SEED_MODULE = "seed"


def _slices[T](items: Sequence[T]) -> Iterator[Sequence[T]]:
    for start in range(0, len(items), SLICE):
        yield items[start : start + SLICE]


async def rescore(
    session: AsyncSession, profile_id: int, ids: Iterable[int] | None = None
) -> list[Entity]:
    """Recomputes the scores of these traces (all of the profile's when `ids` is None) and
    returns the ones whose scores changed."""
    if ids is None:
        entities = list(
            await session.scalars(select(Entity).where(Entity.profile_id == profile_id))
        )
        edges = list(await session.scalars(select(Edge).where(Edge.profile_id == profile_id)))
    else:
        wanted = sorted(set(ids))
        entities = []
        edges_by_id: dict[int, Edge] = {}
        for part in _slices(wanted):
            entities += await session.scalars(select(Entity).where(Entity.id.in_(part)))
            for edge in await session.scalars(
                select(Edge).where(or_(Edge.source_id.in_(part), Edge.target_id.in_(part)))
            ):
                edges_by_id[edge.id] = edge
        edges = list(edges_by_id.values())
    if not entities:
        return []

    known = {e.id: e for e in entities}
    others = sorted({i for edge in edges for i in (edge.source_id, edge.target_id)} - known.keys())
    for part in _slices(others):
        for entity in await session.scalars(select(Entity).where(Entity.id.in_(part))):
            known[entity.id] = entity

    if ids is None:
        declared = {e.target_id for e in edges if e.module == SEED_MODULE}
    else:
        declared = set()
        everyone = sorted(known)
        for part in _slices(everyone):
            declared.update(
                await session.scalars(
                    select(Edge.target_id).where(
                        Edge.module == SEED_MODULE, Edge.target_id.in_(part)
                    )
                )
            )

    modules: defaultdict[int, set[str]] = defaultdict(set)
    for part in _slices(sorted(e.id for e in entities)):
        rows = await session.execute(
            select(Evidence.entity_id, Evidence.module)
            .where(Evidence.entity_id.in_(part))
            .distinct()
        )
        for entity_id, module in rows:
            modules[entity_id].add(module)

    links: defaultdict[int, list[Link]] = defaultdict(list)
    for edge in edges:
        if edge.source_id == edge.target_id:
            continue
        for this, other_id, incoming in (
            (edge.target_id, edge.source_id, True),
            (edge.source_id, edge.target_id, False),
        ):
            other = known.get(other_id)
            if other is None:
                continue
            links[this].append(
                Link(
                    relation=edge.relation,
                    module=edge.module,
                    other=_neighbour(other, other.id in declared),
                    incoming=incoming,
                )
            )

    changed: list[Entity] = []
    for entity in entities:
        scores = score(
            Trace(
                kind=EntityKind(entity.kind),
                status=EntityStatus(entity.status),
                declared=entity.id in declared,
                normalized=entity.normalized,
                module_confidence=entity.module_confidence,
                modules=frozenset(modules[entity.id]),
                attributes=entity.attributes or {},
                links=tuple(links[entity.id]),
            )
        )
        reasons: dict[str, Any] = scores.reasons_json()
        if (entity.confidence, entity.risk, entity.score_reasons) != (
            scores.confidence,
            scores.risk,
            reasons,
        ):
            entity.confidence = scores.confidence
            entity.risk = scores.risk
            entity.score_reasons = reasons
            changed.append(entity)
    return changed


def _neighbour(entity: Entity, declared: bool) -> Neighbour:
    return Neighbour(
        kind=EntityKind(entity.kind),
        status=EntityStatus(entity.status),
        declared=declared,
        display=entity.display,
    )


async def neighbours(session: AsyncSession, entity_id: int) -> list[int]:
    """The traces linked to this one, either way."""
    rows = await session.execute(
        select(Edge.source_id, Edge.target_id).where(
            or_(Edge.source_id == entity_id, Edge.target_id == entity_id)
        )
    )
    return sorted({i for pair in rows for i in pair} - {entity_id})
