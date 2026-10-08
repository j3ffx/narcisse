"""Vocabulary shared by the storage, the engine, the modules and the API."""

from enum import StrEnum


class ProfileKind(StrEnum):
    PERSONAL = "personal"
    PROFESSIONAL = "professional"
    MIXED = "mixed"


class EntityKind(StrEnum):
    """What a node of the graph is. Seeds use a subset of these kinds."""

    IDENTITY = "identity"
    NAME = "name"
    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    DOMAIN = "domain"
    ORGANIZATION = "organization"
    ACCOUNT = "account"
    URL = "url"
    LEAK = "leak"
    PHOTO = "photo"


SEED_KINDS = frozenset(
    {
        EntityKind.NAME,
        EntityKind.USERNAME,
        EntityKind.EMAIL,
        EntityKind.PHONE,
        EntityKind.ADDRESS,
        EntityKind.DOMAIN,
        EntityKind.ORGANIZATION,
        EntityKind.ACCOUNT,
    }
)


class SeedStatus(StrEnum):
    WATCH = "watch"
    IGNORE = "ignore"


class EntityStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"


class ScanStatus(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    DONE = "done"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"
    DONE = "done"
    CANCELLED = "cancelled"


FINISHED_RUN_STATUSES = frozenset({RunStatus.FAILED, RunStatus.DONE, RunStatus.CANCELLED})


class IntrusionLevel(StrEnum):
    PASSIVE = "passive"
    LIGHT_ACTIVE = "light_active"
