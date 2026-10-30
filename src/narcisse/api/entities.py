"""Traces, as the user reviews them (it's me, it's not me, not sure yet) or adds them by hand, and
the leads among them (traces that could become new elements of the profile)."""

from fastapi import APIRouter
from sqlalchemy import select

from narcisse import notes
from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityKind, EntityStatus
from narcisse.engine import pivot
from narcisse.engine.engine import IDENTITY_KEY, upsert_edge, upsert_entity
from narcisse.engine.events import Transaction
from narcisse.engine.rescore import neighbours, rescore
from narcisse.errors import AppError, not_found
from narcisse.modules._text import is_profile
from narcisse.normalize import normalize
from narcisse.schemas import EntityOut, EntityPatch, LeadOut, TraceIn
from narcisse.storage.models import Edge, Entity, Evidence, Profile, Seed

router = APIRouter(tags=["entities"])

# What the user declared themselves: never up for review.
FIXED_KINDS = frozenset({EntityKind.IDENTITY})
MAX_LEADS = 50


def _emit(tx: Transaction, out: EntityOut, profile_id: int) -> None:
    # The status belongs to the profile, not to one scan: every page showing it follows.
    tx.emit("entity.updated", {**out.model_dump(mode="json"), "profile_id": profile_id}, None)


async def review(
    tx: Transaction,
    entity: Entity,
    status: EntityStatus | None = None,
    pivot_dismissed: bool | None = None,
) -> EntityOut:
    """The user's word on a trace (theirs or not, or not suggested any more), with the scores it
    changes. Also how an assistant's verdict the user accepts is applied."""
    if status is not None:
        if entity.kind in FIXED_KINDS:
            raise AppError("entity_not_reviewable", status=409)
        entity.status = status
    if pivot_dismissed is not None:
        entity.pivot_dismissed = pivot_dismissed
    await tx.session.flush()
    # The user's word changes this trace's scores, and its neighbours' (a trace only reached
    # through one the user rejects is doubted too).
    touched = [entity.id, *await neighbours(tx.session, entity.id)]
    changed = await rescore(tx.session, entity.profile_id, touched)
    for other in changed:
        if other.id != entity.id:
            _emit(tx, EntityOut.model_validate(other), other.profile_id)
    out = EntityOut.model_validate(entity)
    _emit(tx, out, entity.profile_id)
    return out


@router.patch("/entities/{entity_id}")
async def review_entity(entity_id: int, body: EntityPatch, s: ServicesDep) -> EntityOut:
    async with s.bus.transaction() as tx:
        entity = await tx.session.get(Entity, entity_id)
        if entity is None:
            raise not_found("entity")
        return await review(tx, entity, body.status, body.pivot_dismissed)


@router.get("/profiles/{profile_id}/leads")
async def list_leads(profile_id: int, s: ServicesDep) -> list[LeadOut]:
    """Traces sure enough to search from, that aren't elements yet: the surest first."""
    async with s.db.snapshot() as session:
        if await session.get(Profile, profile_id) is None:
            raise not_found("profile")
        seeds = {
            (kind, normalized)
            for kind, normalized in await session.execute(
                select(Seed.kind, Seed.normalized).where(Seed.profile_id == profile_id)
            )
        }
        candidates = await session.scalars(
            select(Entity)
            .where(
                Entity.profile_id == profile_id,
                Entity.kind.in_(pivot.PIVOT_KINDS),
                Entity.status != EntityStatus.FALSE_POSITIVE,
                Entity.pivot_dismissed.is_(False),
            )
            .order_by(Entity.confidence.desc(), Entity.risk.desc(), Entity.id)
        )
        leads = [e for e in candidates if pivot.is_lead(e, (e.kind, e.normalized) in seeds)][
            :MAX_LEADS
        ]
        out = []
        for lead in leads:
            row = (
                await session.execute(
                    select(Entity, Edge.relation)
                    .join(Edge, Edge.source_id == Entity.id)
                    .where(
                        Edge.target_id == lead.id,
                        Edge.module != "seed",
                        Entity.kind != EntityKind.IDENTITY,
                    )
                    .order_by(Edge.id)
                    .limit(1)
                )
            ).first()
            via, relation = row if row is not None else (None, None)
            out.append(
                LeadOut(
                    entity=EntityOut.model_validate(lead),
                    via=EntityOut.model_validate(via) if via is not None else None,
                    relation=relation,
                )
            )
        return out


@router.post("/profiles/{profile_id}/traces", status_code=201)
async def add_trace(profile_id: int, body: TraceIn, s: ServicesDep) -> EntityOut:
    """A page the user found themselves: a trace of theirs, related to their identity, with
    what they noted as its proof."""
    kind = EntityKind.ACCOUNT if is_profile(body.url.strip()) else EntityKind.URL
    display, normalized = normalize(kind, body.url)
    now = s.engine.clock.now()
    async with s.bus.transaction() as tx:
        profile = await tx.session.get(Profile, profile_id)
        if profile is None:
            raise not_found("profile")
        identity = await upsert_entity(
            tx.session,
            profile_id=profile_id,
            kind=EntityKind.IDENTITY,
            display=profile.name,
            normalized=IDENTITY_KEY,
            now=now,
            status=EntityStatus.CONFIRMED,
        )
        entity = await upsert_entity(
            tx.session,
            profile_id=profile_id,
            kind=kind,
            display=display,
            normalized=normalized,
            now=now,
            status=EntityStatus.CONFIRMED,
        )
        entity.status = EntityStatus.CONFIRMED  # found by the user: it's them
        edge = await upsert_edge(
            tx.session,
            profile_id=profile_id,
            source_id=identity.id,
            target_id=entity.id,
            relation="added_by_hand",
            module="manual",
            now=now,
            confidence=1.0,
        )
        note = " ".join((body.note or "").split())
        tx.session.add(
            Evidence(
                entity_id=entity.id,
                edge_id=edge.id,
                scan_id=None,
                run_id=None,
                module="manual",
                url=display,
                note=None if note else notes.note("added_by_hand"),
                excerpt=note or None,
                content_hash=None,
                captured_at=now,
            )
        )
        await tx.session.flush()
        touched = [entity.id, *await neighbours(tx.session, entity.id)]
        for other in await rescore(tx.session, profile_id, touched):
            if other.id != entity.id:
                _emit(tx, EntityOut.model_validate(other), other.profile_id)
        out = EntityOut.model_validate(entity)
        _emit(tx, out, entity.profile_id)
    return out
