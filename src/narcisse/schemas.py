"""Shapes the API returns and the events carry (the UI's TypeScript types mirror them)."""

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from narcisse.domain import (
    CheckOutcome,
    EntityKind,
    EntityStatus,
    ProfileKind,
    RequestStatus,
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
    # Scan again on its own (with those modules) while Narcisse runs.
    rescan: Literal["never", "weekly", "monthly"] = "never"


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
    # Since when no scan finds it (every search that found it ran again and saw nothing).
    gone_at: datetime | None = None


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
    ui_lang: Literal["auto", "fr", "en"]
    github_token_set: bool
    gitlab_token_set: bool
    exclude_adult: bool
    fediverse_instances: list[str]
    searxng_url: str | None
    searxng_autostart: bool
    llm_provider: str
    llm_model: str | None
    llm_url: str | None
    llm_key_set: bool
    llm_remote_ok: bool


class PreferencesPatch(Schema):
    # The language Narcisse speaks ("auto": the browser's, else the system's).
    ui_lang: Literal["auto", "fr", "en"] | None = None
    # An empty string (or null) removes the token.
    github_token: str | None = Field(default=None, max_length=200)
    gitlab_token: str | None = Field(default=None, max_length=200)
    exclude_adult: bool | None = None
    # Host names, or addresses of the instances (https://example.social/…).
    fediverse_instances: list[str] | None = Field(default=None, max_length=50)
    # The address of the user's SearXNG instance; an empty string (or null) removes it.
    searxng_url: str | None = Field(default=None, max_length=200)
    searxng_autostart: bool | None = None
    llm_provider: Literal["none", "claude_code", "local", "openai", "demo"] | None = None
    # An empty string (or null) goes back to the provider's default model.
    llm_model: str | None = Field(default=None, max_length=100)
    # The local server's or the service's address; its key (empty or null removes it).
    llm_url: str | None = Field(default=None, max_length=200)
    llm_key: str | None = Field(default=None, max_length=500)
    llm_remote_ok: bool | None = None


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


class RequestOut(Schema):
    """An action the user follows on a trace, and where it stands."""

    id: int
    profile_id: int
    entity: EntityOut
    action: str
    service: str  # "" when no site is named
    letter: str | None
    recipient: str | None
    subject: str | None
    body: str | None
    status: RequestStatus
    note: str | None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    reminded_at: datetime | None
    closed_at: datetime | None
    check: CheckOutcome | None  # what the last scan that looked again saw
    checked_at: datetime | None
    check_scan_id: int | None
    reminder_at: datetime | None  # when it deserves a reminder (a month after sending)
    due: bool  # that time has come


class RequestIn(Schema):
    """Following an action of a trace's sheet (a request sent, an account to delete…)."""

    action: str = Field(min_length=1, max_length=50)
    service: str = Field(default="", max_length=200)
    letter: str | None = Field(default=None, max_length=30)
    recipient: str | None = Field(default=None, max_length=320)
    subject: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=20_000)
    status: RequestStatus = RequestStatus.TODO


class RequestPatch(Schema):
    status: RequestStatus | None = None
    recipient: str | None = Field(default=None, max_length=320)
    note: str | None = Field(default=None, max_length=2000)
    reminded: bool | None = None  # True: the user just sent a reminder


class ExposurePoint(Schema):
    taken_at: datetime
    scan_id: int | None
    levels: dict[str, int]
    exposure: float


class ExposureOut(Schema):
    """How exposed a profile is now, how it went scan after scan, and where its requests are."""

    levels: dict[str, int]  # traces per risk level
    exposure: float  # the sum of their risks
    history: list[ExposurePoint]
    requests: dict[str, int]  # per status
    due: int  # requests to remind
    gone: int  # traces a scan no longer found after the user acted


class DueOut(Schema):
    """Requests due for a reminder, for the tray's daily notice."""

    count: int


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
    request: RequestOut | None  # the user follows it


class RemediationOut(Schema):
    actions: list[ActionOut]
    complaint: GuideOut  # where to turn when a request goes unanswered


class ExternalLinkIn(Schema):
    """A page to open in the user's own browser (a link clicked in Narcisse's window)."""

    url: str = Field(max_length=4000)


class DiffOut(Schema):
    """What changed from one scan to a later one."""

    before: ScanOut
    after: ScanOut
    new: list[EntityOut]  # seen for the first time
    gone: list[EntityOut]  # every search that found them ran again and saw nothing
    unchecked: list[EntityOut]  # not seen again, but their searches didn't all run again
    modified: list[EntityOut]  # their page changed


class BackupIn(Schema):
    # Seals the backup (and then keeps the tokens in it); empty: a plain backup, without tokens.
    passphrase: str | None = Field(default=None, max_length=500)


class RestoreIn(Schema):
    data: str  # the backup file, in base64 (state-changing requests carry JSON only)
    passphrase: str | None = Field(default=None, max_length=500)


class RestoreOut(Schema):
    profiles: int
    created_at: str
    narcisse: str  # the version that made the backup
    safety: str  # where the data before the restore was kept


class ErrorOut(Schema):
    code: str
    params: dict[str, Any] = Field(default_factory=dict)


class PasswordRangeOut(Schema):
    """The hashes Pwned Passwords knows that start like the one asked: (suffix, times seen)."""

    suffixes: list[tuple[str, int]]


AnnotationTask = Literal["triage", "explain", "letter", "leads"]
AnnotationDecision = Literal["pending", "accepted", "dismissed"]


class AnnotationOut(Schema):
    """What the assistant said about a trace, and what was sent to it."""

    id: int
    entity_id: int
    task: AnnotationTask
    provider: str
    model: str | None
    prompt: str
    output: dict[str, Any] | None
    edited: bool
    state: Literal["queued", "running", "done", "failed"]
    error_code: str | None
    error_params: dict[str, Any] | None
    decision: AnnotationDecision
    created_at: datetime
    finished_at: datetime | None


class AnnotationIn(Schema):
    # A letter is asked with its text (`LetterIn`).
    task: Literal["triage", "explain", "leads"]


class LetterIn(Schema):
    """A letter to adapt: as the user has it now, what they want added, and the tone."""

    subject: str = Field(max_length=500)
    body: str = Field(min_length=1, max_length=20_000)
    context: str | None = Field(default=None, max_length=500)
    tone: Literal["courteous", "firm"] = "courteous"


class AiLeadOut(Schema):
    """An element the assistant read in a trace's proofs, not declared yet."""

    annotation_id: int
    index: int  # its place in the answer
    source: EntityOut  # the trace it was read in
    kind: EntityKind
    value: str
    reason: str


class AnnotationPatch(Schema):
    # accepted: a verdict is applied to the trace's status; dismissed: hidden.
    decision: AnnotationDecision | None = None
    # The user's rewrite of an explanation (the same shape as the assistant's answer).
    output: dict[str, Any] | None = None


class PromptOut(Schema):
    """The exact text a question about a trace would send."""

    text: str


class AssistantOut(Schema):
    provider: str  # "none" when no assistant is chosen
    providers: list[str]  # the ones this side offers (demo mode: the demo one only)
    model: str | None
    models: list[str]  # the models the provider can be asked to use
    remote: bool  # what is sent leaves the machine
    remote_ok: bool  # the user agreed to that
    available: bool
    reason: str | None  # why not available (an error code)


class TriageOut(Schema):
    count: int  # traces asked about (or that would be)
    capped: bool  # more were waiting for a review than one batch takes


class TryOut(Schema):
    model: str | None


class GpuOut(Schema):
    name: str
    memory_gb: float | None
    dedicated: bool


class LocalServerOut(Schema):
    name: str
    url: str
    models: list[str]


class RecommendationOut(Schema):
    model: str
    size_gb: float
    speed: Literal["fast", "processor", "slow"]


class MachineOut(Schema):
    """What this machine can run, the model that suits it, and the model servers running."""

    system: str
    memory_gb: float | None
    cores: int | None
    gpus: list[GpuOut]
    unified: bool
    recommended: RecommendationOut
    servers: list[LocalServerOut]


class PullIn(Schema):
    model: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:/-]+$")


class PullOut(Schema):
    model: str | None
    status: Literal["idle", "pulling", "done", "failed", "cancelled"]
    completed: int
    total: int
    error_code: str | None
