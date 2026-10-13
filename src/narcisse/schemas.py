"""Shapes the API returns and the events carry (the UI's TypeScript types mirror them)."""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    notes: dict[str, int] | None
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
    attributes: dict[str, Any]


class EntityPatch(Schema):
    status: EntityStatus


class EdgeOut(Schema):
    """How two traces relate: `source` led to `target`, according to `module`."""

    id: int
    source_id: int
    target_id: int
    relation: str
    module: str
    confidence: float | None
    first_seen: datetime
    last_seen: datetime


class ResultOut(Schema):
    """One finding of a scan: the entity, the proof, and where it came from."""

    id: int  # evidence id
    profile_id: int
    scan_id: int
    run_id: int
    module: str
    entity: EntityOut
    edge: EdgeOut | None
    relation: str | None
    confidence: float | None
    url: str | None
    excerpt: str | None
    captured_at: datetime


class GraphNode(EntityOut):
    first_seen: datetime
    last_seen: datetime
    modules: list[str]  # the sources that found it ("seed" for what the user declared)
    evidence_count: int


class GraphOut(Schema):
    """A profile's traces and how they relate. `truncated`: too many to send them all."""

    nodes: list[GraphNode]
    edges: list[EdgeOut]
    truncated: bool


class EvidenceOut(Schema):
    id: int
    scan_id: int
    run_id: int
    module: str
    relation: str | None
    url: str | None
    excerpt: str | None
    content_hash: str | None
    captured_at: datetime


class EntityDetail(Schema):
    """One trace, with every proof of it and every trace it relates to."""

    entity: GraphNode
    evidence: list[EvidenceOut]
    edges: list[EdgeOut]
    neighbours: list[EntityOut]


class SavedViewIn(Schema):
    name: str = Field(min_length=1, max_length=100)
    # What the UI restores: its shape is the UI's business; only its size is bounded here.
    state: dict[str, Any]

    @field_validator("name")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("empty name")
        return value

    @field_validator("state")
    @classmethod
    def _small(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value)) > 100_000:
            raise ValueError("state too large")
        return value


class SavedViewOut(Schema):
    id: int
    profile_id: int
    name: str
    state: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ClientError(Schema):
    """What the UI reports of a crash: for the log, never stored elsewhere."""

    message: str = Field(max_length=2000)
    stack: str | None = Field(default=None, max_length=20_000)
    where: str = Field(default="", max_length=500)


class DemoGraphIn(Schema):
    nodes: int = Field(default=5000, ge=10, le=20_000)


class DemoGraphOut(Schema):
    profile_id: int


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
    other_hosts: str
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


class PreferencesOut(Schema):
    github_token_set: bool
    gitlab_token_set: bool
    exclude_adult: bool
    fediverse_instances: list[str]


class PreferencesPatch(Schema):
    # An empty string (or null) removes the token.
    github_token: str | None = Field(default=None, max_length=200)
    gitlab_token: str | None = Field(default=None, max_length=200)
    exclude_adult: bool | None = None
    # Host names, or addresses of the instances (https://example.social/…).
    fediverse_instances: list[str] | None = Field(default=None, max_length=50)


class ErrorOut(Schema):
    code: str
    params: dict[str, Any] = Field(default_factory=dict)
