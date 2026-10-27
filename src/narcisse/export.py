"""A profile's complete export: everything Narcisse knows of it, in one JSON document the user
keeps or reads elsewhere. The UI turns it into the CSV of the traces and the HTML report.

The format is named and versioned (`narcisse-export`, 1) so that a later version can read it.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from narcisse import __version__
from narcisse.api.remediation import request_out
from narcisse.engine.engine import scan_detail
from narcisse.errors import not_found
from narcisse.remediation import follow
from narcisse.schemas import EdgeOut, EntityOut, EvidenceOut, ProfileDetail, ScoreReasons
from narcisse.storage.models import (
    Edge,
    Entity,
    Evidence,
    ExposureSnapshot,
    Profile,
    RemovalRequest,
    Scan,
)

FORMAT = "narcisse-export"
VERSION = 1


async def profile_export(session: AsyncSession, profile_id: int, now: datetime) -> dict[str, Any]:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise not_found("profile")
    entities = list(
        await session.scalars(
            select(Entity).where(Entity.profile_id == profile_id).order_by(Entity.id)
        )
    )
    evidence = list(
        await session.scalars(
            select(Evidence)
            .join(Entity, Evidence.entity_id == Entity.id)
            .where(Entity.profile_id == profile_id)
            .order_by(Evidence.id)
        )
    )
    edges = await session.scalars(
        select(Edge).where(Edge.profile_id == profile_id).order_by(Edge.id)
    )
    scans = await session.scalars(
        select(Scan).where(Scan.profile_id == profile_id).order_by(Scan.id)
    )
    requests = await session.scalars(
        select(RemovalRequest)
        .where(RemovalRequest.profile_id == profile_id)
        .order_by(RemovalRequest.id)
    )
    snapshots = await session.scalars(
        select(ExposureSnapshot)
        .where(ExposureSnapshot.profile_id == profile_id)
        .order_by(ExposureSnapshot.taken_at, ExposureSnapshot.id)
    )
    modules: dict[int, set[str]] = {}
    proofs: dict[int, int] = {}
    for proof in evidence:
        modules.setdefault(proof.entity_id, set()).add(proof.module)
        proofs[proof.entity_id] = proofs.get(proof.entity_id, 0) + 1
    levels, exposure = await follow.exposure(session, profile_id)

    def trace(entity: Entity) -> dict[str, Any]:
        return {
            **EntityOut.model_validate(entity).model_dump(mode="json"),
            "first_seen": entity.first_seen.isoformat(),
            "last_seen": entity.last_seen.isoformat(),
            "modules": sorted(modules.get(entity.id, ())),
            "evidence_count": proofs.get(entity.id, 0),
            "reasons": ScoreReasons.model_validate(entity.score_reasons or {}).model_dump(
                mode="json"
            ),
        }

    return {
        "format": FORMAT,
        "version": VERSION,
        "narcisse": __version__,
        "exported_at": now.isoformat(),
        "profile": ProfileDetail.model_validate(profile).model_dump(mode="json"),
        "exposure": {"levels": levels, "exposure": exposure},
        "traces": [trace(e) for e in entities],
        "links": [EdgeOut.model_validate(e).model_dump(mode="json") for e in edges],
        "evidence": [
            {
                **EvidenceOut.model_validate({**vars(proof), "relation": None}).model_dump(
                    mode="json", exclude={"relation"}
                ),
                "entity_id": proof.entity_id,
            }
            for proof in evidence
        ],
        "scans": [scan_detail(scan).model_dump(mode="json") for scan in scans],
        "requests": [request_out(r, now).model_dump(mode="json") for r in requests],
        "history": [
            {
                "taken_at": shot.taken_at.isoformat(),
                "scan_id": shot.scan_id,
                "levels": shot.levels,
                "exposure": shot.exposure,
            }
            for shot in snapshots
        ],
    }
