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
    # The entity the module works on (a seed's entity, later any pivot).
    input_entity_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"))
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
    confidence: Mapped[float | None] = mapped_column(Float)
    risk: Mapped[float | None] = mapped_column(Float)
    attributes: Mapped[dict[str, Any]] = mapped_column(default=dict)
    first_seen: Mapped[datetime]
    last_seen: Mapped[datetime]


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
    scan_id: Mapped[int] = mapped_column(ForeignKey("scan.id", ondelete="CASCADE"))
    run_id: Mapped[int] = mapped_column(ForeignKey("module_run.id", ondelete="CASCADE"))
    module: Mapped[str] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(String(2000))
    excerpt: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    captured_at: Mapped[datetime]


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
