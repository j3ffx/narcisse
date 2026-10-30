"""Tables. Changing one needs an Alembic migration in `storage/migrations/versions/`."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class UTCDateTime(TypeDecorator[datetime]):
    """Aware UTC datetimes in, aware UTC datetimes out (SQLite keeps no time zone)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    type_annotation_map = {datetime: UTCDateTime, dict[str, Any]: JSON, list[Any]: JSON}


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    # Pivot depth, enabled modules… (validated by the API schema).
    settings: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    seeds: Mapped[list["Seed"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="Seed.id",
    )


class Seed(Base):
    """A piece of identity the user gave: what scans start from."""

    __tablename__ = "seed"
    __table_args__ = (UniqueConstraint("profile_id", "kind", "normalized"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    value: Mapped[str] = mapped_column(String(500))
    normalized: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime]

    profile: Mapped[Profile] = relationship(back_populates="seeds")


class Scan(Base):
    __tablename__ = "scan"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    modules: Mapped[list[Any]] = mapped_column(default=list)
    results_count: Mapped[int] = mapped_column(default=0)
    # What the scan reports as a whole ("pivots": traces it followed, "pivots_capped": left).
    notes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]

    profile: Mapped[Profile] = relationship(lazy="joined")
    runs: Mapped[list["ModuleRun"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="ModuleRun.id",
    )


class ModuleRun(Base):
    """One module working on one input: the unit the engine schedules, pauses and retries."""

    __tablename__ = "module_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scan.id", ondelete="CASCADE"), index=True)
    module: Mapped[str] = mapped_column(String(100))
    # The entity the module works on: a seed's entity, or a trace the scan pivoted to.
    input_entity_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"))
    # How many hops from the profile's elements its input is (0: an element).
    depth: Mapped[int] = mapped_column(default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), index=True)
    progress_done: Mapped[int | None]
    progress_total: Mapped[int | None]
    results_count: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)
    # When a queued or rate-limited run may start again.
    retry_at: Mapped[datetime | None]
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    # What the module needs to pick up where it stopped (opaque to the engine).
    checkpoint: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Counters the module reports along the way ("checked": 640, "unreachable": 12…).
    notes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    updated_at: Mapped[datetime]

    scan: Mapped[Scan] = relationship(back_populates="runs")
    input_entity: Mapped["Entity"] = relationship(lazy="joined")


class Entity(Base):
    """A node of the graph: a piece of identity, found or given, unique per profile."""

    __tablename__ = "entity"
    __table_args__ = (UniqueConstraint("profile_id", "kind", "normalized"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    normalized: Mapped[str] = mapped_column(String(1000))
    display: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20))
    # The highest confidence a source gave (0..1); `confidence` and `risk` are the scores
    # computed from it and from the trace's links (engine/scoring.py), with their reasons.
    module_confidence: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    risk: Mapped[float | None] = mapped_column(Float)
    score_reasons: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # The user doesn't want this trace suggested as a new element.
    pivot_dismissed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    attributes: Mapped[dict[str, Any]] = mapped_column(default=dict)
    first_seen: Mapped[datetime]
    last_seen: Mapped[datetime]
    # Since when no scan finds it: every search that found it ran again, without error, and saw
    # nothing. Cleared when a scan finds it again.
    gone_at: Mapped[datetime | None]


class Edge(Base):
    """How two entities are related, and which module said so."""

    __tablename__ = "edge"
    __table_args__ = (UniqueConstraint("source_id", "target_id", "relation", "module"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(50))
    module: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    first_seen: Mapped[datetime]
    last_seen: Mapped[datetime]


class Evidence(Base):
    """Why an entity was found: where, when, what the page said."""

    __tablename__ = "evidence"
    __table_args__ = (Index("ix_evidence_scan_id_id", "scan_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"), index=True)
    edge_id: Mapped[int | None] = mapped_column(ForeignKey("edge.id", ondelete="SET NULL"))
    # None for a trace the user added by hand: no scan found it.
    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scan.id", ondelete="CASCADE"))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("module_run.id", ondelete="CASCADE"))
    module: Mapped[str] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(String(2000))
    excerpt: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    captured_at: Mapped[datetime]


class SavedView(Base):
    """A way of looking at a profile's graph the user named: filters, groups, camera…"""

    __tablename__ = "saved_view"
    __table_args__ = (UniqueConstraint("profile_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    # What the UI restores (validated by the UI, which owns its shape).
    state: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class RemovalRequest(Base):
    """An action the user took on a trace (a request sent, an account deleted…), followed until
    the trace is gone."""

    __tablename__ = "removal_request"
    __table_args__ = (UniqueConstraint("entity_id", "action", "service"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(50))  # the action sheet's code
    service: Mapped[str] = mapped_column(String(200), default="")  # "" when no site is named
    letter: Mapped[str | None] = mapped_column(String(30))
    recipient: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str | None] = mapped_column(Text)  # the text as the user sent it
    status: Mapped[str] = mapped_column(String(20), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    sent_at: Mapped[datetime | None]
    reminded_at: Mapped[datetime | None]  # the last reminder the user sent
    closed_at: Mapped[datetime | None]  # done or refused
    # What the last scan that looked for the trace again saw ("gone", "still_there").
    check: Mapped[str | None] = mapped_column(String(20))
    checked_at: Mapped[datetime | None]
    check_scan_id: Mapped[int | None] = mapped_column(ForeignKey("scan.id", ondelete="SET NULL"))

    entity: Mapped[Entity] = relationship(lazy="joined")


class ExposureSnapshot(Base):
    """A profile's exposure as a finished scan left it: how many traces at each risk level."""

    __tablename__ = "exposure_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scan.id", ondelete="SET NULL"))
    taken_at: Mapped[datetime]
    levels: Mapped[dict[str, Any]]  # {"low": 12, "medium": 4, "high": 2, "critical": 1}
    exposure: Mapped[float]  # the sum of the traces' risks (0..1 each)


class Annotation(Base):
    """What the user's assistant (an LLM they chose) said about a trace, asked by the user, kept
    with what was sent. It changes nothing until the user accepts it."""

    __tablename__ = "llm_annotation"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"), index=True)
    task: Mapped[str] = mapped_column(String(20))  # "triage", "explain"
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt: Mapped[str] = mapped_column(Text)  # exactly what was sent
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)  # the user rewrote the output
    state: Mapped[str] = mapped_column(String(10), index=True)  # queued, running, done, failed
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(10))  # pending, accepted, dismissed
    created_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]


class Event(Base):
    """Everything the UI is told, kept so that a reconnecting browser misses nothing."""

    __tablename__ = "event"
    # Ids are never reused, even once old events are pruned: browsers resume from them.
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(50))
    scan_id: Mapped[int | None] = mapped_column(index=True)
    payload: Mapped[dict[str, Any]]
    created_at: Mapped[datetime] = mapped_column(index=True)
