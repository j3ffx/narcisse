"""Traces, as the user reviews them (it's me, it's not me, not sure yet) or adds them by hand."""

from fastapi import APIRouter

from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityKind, EntityStatus
from narcisse.engine.engine import IDENTITY_KEY, upsert_edge, upsert_entity
from narcisse.errors import AppError, not_found
from narcisse.modules._text import is_profile
from narcisse.normalize import normalize
from narcisse.schemas import EntityOut, EntityPatch, TraceIn
from narcisse.storage.models import Entity, Evidence, Profile

router = APIRouter(tags=["entities"])

# What the user declared themselves: never up for review.
FIXED_KINDS = frozenset({EntityKind.IDENTITY})


@router.patch("/entities/{entity_id}")
async def review_entity(entity_id: int, body: EntityPatch, s: ServicesDep) -> EntityOut:
    async with s.bus.transaction() as tx:
        entity = await tx.session.get(Entity, entity_id)
        if entity is None:
            raise not_found("entity")
        if entity.kind in FIXED_KINDS:
            raise AppError("entity_not_reviewable", status=409)
        entity.status = body.status
        out = EntityOut.model_validate(entity)
        # The status belongs to the profile, not to one scan: every page showing it follows.
        tx.emit(
            "entity.updated", {**out.model_dump(mode="json"), "profile_id": entity.profile_id}, None
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
            confidence=1.0,
        )
        entity = await upsert_entity(
            tx.session,
            profile_id=profile_id,
            kind=kind,
            display=display,
            normalized=normalized,
            now=now,
            status=EntityStatus.CONFIRMED,
            confidence=1.0,
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
                excerpt=note or "Ajoutée par toi.",
                content_hash=None,
                captured_at=now,
            )
        )
        await tx.session.flush()
        out = EntityOut.model_validate(entity)
        tx.emit("entity.updated", {**out.model_dump(mode="json"), "profile_id": profile_id}, None)
    return out
