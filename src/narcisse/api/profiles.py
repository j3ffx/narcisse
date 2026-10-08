"""Profiles and their seeds."""

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from narcisse.api.deps import ServicesDep
from narcisse.domain import SEED_KINDS, EntityKind, ScanStatus
from narcisse.errors import AppError, not_found
from narcisse.normalize import normalize
from narcisse.schemas import (
    ProfileDetail,
    ProfileIn,
    ProfileOut,
    ProfilePatch,
    SeedIn,
    SeedOut,
    SeedPatch,
)
from narcisse.storage.models import Profile, Scan, Seed

router = APIRouter(tags=["profiles"])


@router.get("/profiles")
async def list_profiles(s: ServicesDep) -> list[ProfileOut]:
    async with s.db.read() as session:
        profiles = await session.scalars(select(Profile).order_by(Profile.name, Profile.id))
        return [ProfileOut.model_validate(p) for p in profiles]


@router.post("/profiles", status_code=201)
async def create_profile(body: ProfileIn, s: ServicesDep) -> ProfileDetail:
    now = s.bus.clock.now()
    async with s.db.write() as session:
        profile = Profile(
            name=body.name.strip(),
            kind=body.kind,
            settings=body.settings.model_dump(),
            created_at=now,
            updated_at=now,
            seeds=[],
        )
        session.add(profile)
        await session.flush()
        return ProfileDetail.model_validate(profile)


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: int, s: ServicesDep) -> ProfileDetail:
    async with s.db.read() as session:
        profile = await session.get(Profile, profile_id)
        if profile is None:
            raise not_found("profile")
        return ProfileDetail.model_validate(profile)


@router.patch("/profiles/{profile_id}")
async def update_profile(profile_id: int, body: ProfilePatch, s: ServicesDep) -> ProfileDetail:
    async with s.db.write() as session:
        profile = await session.get(Profile, profile_id)
        if profile is None:
            raise not_found("profile")
        if body.name is not None:
            profile.name = body.name.strip()
        if body.kind is not None:
            profile.kind = body.kind
        if body.settings is not None:
            profile.settings = body.settings.model_dump()
        profile.updated_at = s.bus.clock.now()
        return ProfileDetail.model_validate(profile)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: int, s: ServicesDep) -> Response:
    async with s.db.write() as session:
        profile = await session.get(Profile, profile_id)
        if profile is None:
            raise not_found("profile")
        active = await session.scalar(
            select(Scan.id).where(
                Scan.profile_id == profile_id,
                Scan.status.in_((ScanStatus.RUNNING, ScanStatus.PAUSED)),
            )
        )
        if active is not None:
            raise AppError("profile_busy", status=409)
        await session.delete(profile)
    return Response(status_code=204)


def _checked(kind: str, value: str) -> tuple[str, str]:
    """(display, normalized) of a seed value, or a 422 the UI can explain."""
    if kind not in SEED_KINDS:
        raise AppError("invalid_seed_kind", status=422, params={"kind": kind})
    return normalize(EntityKind(kind), value)


@router.post("/profiles/{profile_id}/seeds", status_code=201)
async def add_seed(profile_id: int, body: SeedIn, s: ServicesDep) -> SeedOut:
    display, normalized = _checked(body.kind, body.value)
    try:
        async with s.db.write() as session:
            if await session.get(Profile, profile_id) is None:
                raise not_found("profile")
            seed = Seed(
                profile_id=profile_id,
                kind=body.kind,
                value=display,
                normalized=normalized,
                status=body.status,
                created_at=s.bus.clock.now(),
            )
            session.add(seed)
            await session.flush()
            return SeedOut.model_validate(seed)
    except IntegrityError as exc:
        raise AppError("seed_exists", status=409) from exc


@router.patch("/seeds/{seed_id}")
async def update_seed(seed_id: int, body: SeedPatch, s: ServicesDep) -> SeedOut:
    try:
        async with s.db.write() as session:
            seed = await session.get(Seed, seed_id)
            if seed is None:
                raise not_found("seed")
            if body.value is not None:
                seed.value, seed.normalized = _checked(seed.kind, body.value)
            if body.status is not None:
                seed.status = body.status
            await session.flush()
            return SeedOut.model_validate(seed)
    except IntegrityError as exc:
        raise AppError("seed_exists", status=409) from exc


@router.delete("/seeds/{seed_id}", status_code=204)
async def delete_seed(seed_id: int, s: ServicesDep) -> Response:
    async with s.db.write() as session:
        seed = await session.get(Seed, seed_id)
        if seed is None:
            raise not_found("seed")
        await session.delete(seed)
    return Response(status_code=204)
