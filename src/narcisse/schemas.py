"""Shapes the API returns and the events carry (the UI's TypeScript types mirror them)."""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from narcisse.domain import (
    EntityKind,
    EntityStatus,
    ProfileKind,
    RunStatus,
    ScanStatus,
    SeedStatus,
)
from narcisse.storage import models


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProfileSettings(Schema):
    # How many hops a scan may follow sure traces by itself (0: it only suggests them).
    pivot_depth: int = Field(default=0, ge=0, le=2)
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
    # 0: one of the profile's elements; more: a trace the scan followed, so many hops away.
    depth: int
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
    # "pivots": traces the scan followed; "capped": traces it would have followed, past its cap.
    notes: dict[str, Any] | None
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
    # Scores, 0..1 (engine/scoring.py); their reasons are in the trace's detail.
    confidence: float | None
    risk: float | None
    attributes: dict[str, Any]


class EntityPatch(Schema):
    status: EntityStatus | None = None
    # True: stop suggesting this trace as a new element.
    pivot_dismissed: bool | None = None


class ScoreReason(Schema):
    """One rule behind a score: a code the UI translates, and what it did to the score."""

    code: str
    points: int | None = None
    factor: float | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ScoreReasons(Schema):
    confidence: list[ScoreReason] = Field(default_factory=list)
    risk: list[ScoreReason] = Field(default_factory=list)


class LeadOut(Schema):
    """A trace that could become one of the profile's elements, and how it was found."""

    entity: EntityOut
    via: EntityOut | None
    relation: str | None


class TraceIn(Schema):
    """A page the user found themselves (through the assisted search, say)."""

    url: str = Field(max_length=2000)
    note: str | None = Field(default=None, max_length=500)


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
    scan_id: int | None  # None: added by hand
    run_id: int | None
    module: str
    relation: str | None
    url: str | None
    excerpt: str | None
    content_hash: str | None
    captured_at: datetime


class EntityDetail(Schema):
    """One trace, with every proof of it and every trace it relates to."""

    entity: GraphNode
    reasons: ScoreReasons
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
    hosts: list[str]
    other_hosts: str
    # Why it can't run with the current settings (an error code), or null.
    unavailable: str | None
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
    searxng_url: str | None
    searxng_autostart: bool


class PreferencesPatch(Schema):
    # An empty string (or null) removes the token.
    github_token: str | None = Field(default=None, max_length=200)
    gitlab_token: str | None = Field(default=None, max_length=200)
    exclude_adult: bool | None = None
    # Host names, or addresses of the instances (https://example.social/…).
    fediverse_instances: list[str] | None = Field(default=None, max_length=50)
    # The address of the user's SearXNG instance; an empty string (or null) removes it.
    searxng_url: str | None = Field(default=None, max_length=200)
    searxng_autostart: bool | None = None


class SearxngOut(Schema):
    """The user's SearXNG: whether Docker is there, whether the instance answers, and how a
    launch asked from the app is going."""

    docker: bool  # Docker is installed
    address: str | None  # the instance the settings name
    running: bool  # an instance answers there (or at the usual address, when none is set)
    state: str  # "idle", "starting", "ready", "failed"
    step: str | None  # while starting: "desktop", "compose", "waiting"
    error: str | None  # when failed: a code the UI explains


class GuideOut(Schema):
    title: str
    url: str


class ServiceOut(Schema):
    """A site the knowledge base knows how to leave (JustDeleteMe, or Narcisse's own sheets)."""

    name: str
    category: str  # "account", "broker", "business_directory", "archive", "keyserver"
    url: str | None
    difficulty: str | None  # "easy", "medium", "hard", "limited", "impossible"
    notes: str | None
    notes_lang: str
    source: str  # "jdm", "narcisse"


class LetterOut(Schema):
    subject: str
    body: str


class ActionOut(Schema):
    """One thing the user can do about a trace; Narcisse prepares it, the user does it."""

    code: str  # what to do (the UI explains it)
    service: ServiceOut | None
    url: str | None
    email: str | None  # whom to write to, when known
    links: list[GuideOut]
    # The letter it prepares, in French and in English, and which one suits the recipient.
    letter: str | None
    letters: dict[str, LetterOut]
    lang: str


class RemediationOut(Schema):
    actions: list[ActionOut]
    complaint: GuideOut  # where to turn when a request goes unanswered


class ExternalLinkIn(Schema):
    """A page to open in the user's own browser (a link clicked in Narcisse's window)."""

    url: str = Field(max_length=4000)


class ErrorOut(Schema):
    code: str
    params: dict[str, Any] = Field(default_factory=dict)


class PasswordRangeOut(Schema):
    """The hashes Pwned Passwords knows that start like the one asked: (suffix, times seen)."""

    suffixes: list[tuple[str, int]]
