"""Traces, as the user reviews them: it's me, it's not me, not sure yet."""

from fastapi import APIRouter

from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityKind
from narcisse.errors import AppError, not_found
from narcisse.schemas import EntityOut, EntityPatch
from narcisse.storage.models import Entity

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
