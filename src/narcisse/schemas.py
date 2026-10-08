"""Shapes the API returns and the events carry (the UI's TypeScript types mirror them)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from narcisse.domain import (
    EntityKind,
    EntityStatus,
    IntrusionLevel,
    ProfileKind,
    RunStatus,
    ScanStatus,
    SeedStatus,
)
from narcisse.storage import models


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProfileSettings(Schema):
    # How many hops a found trace may lead to a new search (0: never on its own).
    pivot_depth: int = Field(default=0, ge=0, le=3)
    # Modules ticked by default when starting a scan; empty means every applicable one.
    modules: list[str] = Field(default_factory=list)


class ProfileIn(Schema):
    name: str = Field(min_length=1, max_length=200)
    kind: ProfileKind = ProfileKind.PERSONAL
    settings: ProfileSettings = Field(default_factory=ProfileSettings)


class ProfilePatch(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: ProfileKind | None = None
    settings: ProfileSettings | None = None


class SeedIn(Schema):
    kind: EntityKind
    value: str = Field(min_length=1, max_length=500)
    status: SeedStatus = SeedStatus.WATCH


class SeedPatch(Schema):
    value: str | None = Field(default=None, min_length=1, max_length=500)
    status: SeedStatus | None = None


class SeedOut(Schema):
    id: int
    profile_id: int
    kind: EntityKind
    value: str
    normalized: str
    status: SeedStatus
    created_at: datetime


class ProfileOut(Schema):
    id: int
    name: str
    kind: ProfileKind
    settings: ProfileSettings
    created_at: datetime
    updated_at: datetime


class ProfileDetail(ProfileOut):
    seeds: list[SeedOut]


class RunOut(Schema):
    id: int
    scan_id: int
    module: str
    input_kind: EntityKind
    input_value: str
    status: RunStatus
    progress_done: int | None
    progress_total: int | None
    results_count: int
    attempts: int
    retry_at: datetime | None
    error_code: str | None
    error_params: dict[str, Any] | None
    retryable: bool
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime

    @classmethod
    def of(cls, run: models.ModuleRun) -> "RunOut":
        return cls.model_validate(
            {
                **{k: getattr(run, k) for k in cls.model_fields if hasattr(run, k)},
                "input_kind": run.input_entity.kind,
                "input_value": run.input_entity.display,
            }
        )


class ScanOut(Schema):
    id: int
    profile_id: int
    profile_name: str
    status: ScanStatus
    modules: list[str]
    results_count: int
    created_at: datetime
    finished_at: datetime | None


class ScanDetail(ScanOut):
    runs: list[RunOut]


class EntityOut(Schema):
    id: int
    kind: EntityKind
    display: str
    normalized: str
    status: EntityStatus
    confidence: float | None


class ResultOut(Schema):
    """One finding of a scan: the entity, the proof, and where it came from."""

    id: int  # evidence id
    scan_id: int
    run_id: int
    module: str
    entity: EntityOut
    relation: str | None
    confidence: float | None
    url: str | None
    excerpt: str | None
    captured_at: datetime


class ResultsPage(Schema):
    items: list[ResultOut]
    total: int


class RateLimitOut(Schema):
    requests: int
    per_seconds: float


class ModuleOut(Schema):
    name: str
    title: str
    description: str
    category: str
    accepts: list[EntityKind]
    produces: list[EntityKind]
    intrusion: IntrusionLevel
    hosts: list[str]
    rate_limit: RateLimitOut | None
    licence: str
    data_source: str
    demo: bool


class ActivityOut(Schema):
    """Everything the activity centre shows, and the event it is up to date with."""

    last_event_id: int
    scans: list[ScanDetail]


class AppInfo(Schema):
    version: str
    demo: bool
    data_dir: str


class ErrorOut(Schema):
    code: str
    params: dict[str, Any] = Field(default_factory=dict)
