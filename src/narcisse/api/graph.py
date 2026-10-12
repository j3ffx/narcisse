"""A profile's traces as a graph, and one trace in detail (its proofs, its neighbours)."""

from collections import defaultdict
from collections.abc import Iterable

from fastapi import APIRouter
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityStatus
from narcisse.errors import not_found
from narcisse.schemas import (
    EdgeOut,
    EntityDetail,
    EntityOut,
    EvidenceOut,
    GraphNode,
    GraphOut,
)
from narcisse.storage.models import Edge, Entity, Evidence, Profile

router = APIRouter(tags=["graph"])

# Beyond that, the graph is sent cut (the most recently seen traces first).
MAX_NODES = 20_000


async def _sources(
    session: AsyncSession, entity_ids: Iterable[int]
) -> dict[int, tuple[list[str], int]]:
    """For each entity: the modules that found it, and how many proofs there are."""
    ids = list(entity_ids)
    found: dict[int, tuple[list[str], int]] = {}
    modules: defaultdict[int, list[str]] = defaultdict(list)
    counts: defaultdict[int, int] = defaultdict(int)
    # SQLite caps the number of bound parameters: ask in slices.
    for start in range(0, len(ids), 900):
        rows = await session.execute(
            select(Evidence.entity_id, Evidence.module, func.count())
            .where(Evidence.entity_id.in_(ids[start : start + 900]))
            .group_by(Evidence.entity_id, Evidence.module)
            .order_by(Evidence.entity_id, Evidence.module)
        )
        for entity_id, module, count in rows:
            modules[entity_id].append(module)
            counts[entity_id] += count
    for entity_id in ids:
        found[entity_id] = (modules[entity_id], counts[entity_id])
    return found


def _node(entity: Entity, sources: tuple[list[str], int], declared: bool) -> GraphNode:
    modules, count = sources
    return GraphNode.model_validate(
        {
            **EntityOut.model_validate(entity).model_dump(),
            "first_seen": entity.first_seen,
            "last_seen": entity.last_seen,
            "modules": (["seed"] if declared else []) + modules,
            "evidence_count": count,
        }
    )


@router.get("/profiles/{profile_id}/graph")
async def get_graph(profile_id: int, s: ServicesDep, false_positives: bool = False) -> GraphOut:
    async with s.db.snapshot() as session:
        if await session.get(Profile, profile_id) is None:
            raise not_found("profile")
        query = select(Entity).where(Entity.profile_id == profile_id)
        if not false_positives:
            query = query.where(Entity.status != EntityStatus.FALSE_POSITIVE)
        entities = list(
            await session.scalars(
                query.order_by(Entity.last_seen.desc(), Entity.id).limit(MAX_NODES + 1)
            )
        )
        truncated = len(entities) > MAX_NODES
        entities = entities[:MAX_NODES]
        kept = {e.id for e in entities}
        edges = [
            edge
            for edge in await session.scalars(
                select(Edge).where(Edge.profile_id == profile_id).order_by(Edge.id)
            )
            if edge.source_id in kept and edge.target_id in kept
        ]
        declared = {e.target_id for e in edges if e.module == "seed"}
        sources = await _sources(session, kept)
        return GraphOut(
            nodes=[_node(e, sources[e.id], e.id in declared) for e in entities],
            edges=[EdgeOut.model_validate(e) for e in edges],
            truncated=truncated,
        )


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: int, s: ServicesDep) -> EntityDetail:
    async with s.db.snapshot() as session:
        entity = await session.get(Entity, entity_id)
        if entity is None:
            raise not_found("entity")
        edges = list(
            await session.scalars(
                select(Edge)
                .where(or_(Edge.source_id == entity_id, Edge.target_id == entity_id))
                .order_by(Edge.id)
            )
        )
        rows = await session.execute(
            select(Evidence, Edge.relation)
            .outerjoin(Edge, Evidence.edge_id == Edge.id)
            .where(Evidence.entity_id == entity_id)
            .order_by(Evidence.captured_at.desc(), Evidence.id.desc())
        )
        evidence = [
            EvidenceOut.model_validate({**vars(proof), "relation": relation})
            for proof, relation in rows
        ]
        others = {e.source_id for e in edges} | {e.target_id for e in edges}
        others.discard(entity_id)
        neighbours = list(
            await session.scalars(select(Entity).where(Entity.id.in_(others)).order_by(Entity.id))
        )
        sources = await _sources(session, [entity_id])
        declared = any(e.module == "seed" and e.target_id == entity_id for e in edges)
        return EntityDetail(
            entity=_node(entity, sources[entity_id], declared),
            evidence=evidence,
            edges=[EdgeOut.model_validate(e) for e in edges],
            neighbours=[EntityOut.model_validate(n) for n in neighbours],
        )
