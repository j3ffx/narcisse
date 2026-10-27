"""A profile's history: what changed between two scans, and its exports."""

from typing import Any

from fastapi import APIRouter

from narcisse import export, history
from narcisse.api.deps import ServicesDep
from narcisse.engine.engine import scan_out
from narcisse.errors import not_found
from narcisse.schemas import DiffOut, EntityOut
from narcisse.storage.models import Entity, Profile

router = APIRouter(tags=["history"])


@router.get("/profiles/{profile_id}/diff")
async def get_diff(
    profile_id: int, s: ServicesDep, before: int | None = None, after: int | None = None
) -> DiffOut:
    """From `before` to `after` (by default, the two last finished scans, checks left out)."""
    async with s.db.snapshot() as session:
        if await session.get(Profile, profile_id) is None:
            raise not_found("profile")
        diff = await history.compare(session, profile_id, before, after)

        def out(entities: list[Entity]) -> list[EntityOut]:
            return [EntityOut.model_validate(e) for e in entities]

        return DiffOut(
            before=scan_out(diff.before),
            after=scan_out(diff.after),
            new=out(diff.new),
            gone=out(diff.gone),
            unchecked=out(diff.unchecked),
            modified=out(diff.modified),
        )


@router.get("/profiles/{profile_id}/export")
async def export_profile(profile_id: int, s: ServicesDep) -> dict[str, Any]:
    """Everything Narcisse knows of the profile (format `narcisse-export`, version 1)."""
    async with s.db.snapshot() as session:
        return await export.profile_export(session, profile_id, s.engine.clock.now())
