"""A profile's traces as a graph, one trace in detail (its proofs, its neighbours), and the views
of the graph the user saved."""

from collections import defaultdict
from collections.abc import Iterable

from fastapi import APIRouter, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from narcisse import demo_graph
from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityStatus
from narcisse.errors import not_found
from narcisse.schemas import (
    DemoGraphIn,
    DemoGraphOut,
    EdgeOut,
    EntityDetail,
    EntityOut,
    EvidenceOut,
    GraphNode,
    GraphOut,
    SavedViewIn,
    SavedViewOut,
    ScoreReasons,
)
from narcisse.storage.models import Edge, Entity, Evidence, Profile, SavedView

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
            reasons=ScoreReasons.model_validate(entity.score_reasons or {}),
            evidence=evidence,
            edges=[EdgeOut.model_validate(e) for e in edges],
            neighbours=[EntityOut.model_validate(n) for n in neighbours],
        )


@router.get("/profiles/{profile_id}/views")
async def list_views(profile_id: int, s: ServicesDep) -> list[SavedViewOut]:
    async with s.db.read() as session:
        if await session.get(Profile, profile_id) is None:
            raise not_found("profile")
        views = await session.scalars(
            select(SavedView).where(SavedView.profile_id == profile_id).order_by(SavedView.name)
        )
        return [SavedViewOut.model_validate(v) for v in views]


@router.post("/profiles/{profile_id}/views", status_code=201)
async def save_view(profile_id: int, body: SavedViewIn, s: ServicesDep) -> SavedViewOut:
    """Saves a view; one of the same name is replaced (saving again updates it)."""
    now = s.bus.clock.now()
    async with s.db.write() as session:
        if await session.get(Profile, profile_id) is None:
            raise not_found("profile")
        view = await session.scalar(
            select(SavedView).where(SavedView.profile_id == profile_id, SavedView.name == body.name)
        )
        if view is None:
            view = SavedView(profile_id=profile_id, name=body.name, created_at=now)
            session.add(view)
        view.state = body.state
        view.updated_at = now
        await session.flush()
        return SavedViewOut.model_validate(view)


@router.delete("/views/{view_id}", status_code=204)
async def delete_view(view_id: int, s: ServicesDep) -> Response:
    async with s.db.write() as session:
        view = await session.get(SavedView, view_id)
        if view is None:
            raise not_found("view")
        await session.delete(view)
    return Response(status_code=204)


@router.post("/demo/graph", status_code=201)
async def make_demo_graph(body: DemoGraphIn, s: ServicesDep) -> DemoGraphOut:
    """A fictitious profile with that many traces (demo mode only: it fills the demo data)."""
    if not s.settings.demo:
        raise not_found("route")
    async with s.db.write() as session:
        profile = await demo_graph.generate(session, size=body.nodes, now=s.bus.clock.now())
        return DemoGraphOut(profile_id=profile.id)
