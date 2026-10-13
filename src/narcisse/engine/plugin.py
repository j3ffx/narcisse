"""What a source module is: its description, what it receives, what it yields, how it fails.

A module is one file in `narcisse/modules/` with one `SourceModule` subclass. Its `meta` drives
the scheduling (accepted kinds, parallel runs, rate limit) and the list of sources shown in the UI.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Protocol

from narcisse.domain import EntityKind, IntrusionLevel

if TYPE_CHECKING:
    from narcisse.engine.http import HttpClient
    from narcisse.preferences import Preferences


@dataclass(frozen=True, kw_only=True)
class RateLimit:
    """At most `requests` requests every `per_seconds` seconds, per domain."""

    requests: int
    per_seconds: float

    @property
    def interval(self) -> float:
        return self.per_seconds / self.requests


@dataclass(frozen=True, kw_only=True)
class ModuleMeta:
    name: str  # stable identifier, e.g. "github.profile"
    title: str  # shown in the UI (French)
    description: str  # what the module does and asks of the source, in one or two sentences
    category: str
    accepts: frozenset[EntityKind]
    produces: frozenset[EntityKind]
    intrusion: IntrusionLevel = IntrusionLevel.PASSIVE
    # Every host the module may contact; `*.example.org` allows one subdomain level.
    hosts: tuple[str, ...] = ()
    # What else it contacts, known only when it runs (in French, for the Sources page): e.g. "le
    # site du domaine fouillé". Each run still declares those hosts (`allowed_hosts`).
    other_hosts: str = ""
    rate_limit: RateLimit | None = None
    max_parallel_runs: int = 2
    licence: str = ""  # licence of reused code or data, if any
    data_source: str = ""  # who provides the data (URL)
    demo: bool = False  # only offered in demo mode


@dataclass(frozen=True, kw_only=True)
class Target:
    """The entity a run works on."""

    entity_id: int
    kind: EntityKind
    value: str
    normalized: str


@dataclass(frozen=True, kw_only=True)
class Finding:
    """One trace found from the target: a new or known entity, how it relates, and the proof."""

    kind: EntityKind
    value: str
    relation: str  # how the target relates to it, e.g. "has_account", "mentioned_on"
    confidence: float | None = None  # how sure the module is that it's the same person, 0..1
    url: str | None = None
    excerpt: str | None = None
    content: str | None = None  # what was read (hashed, never stored)
    attributes: dict[str, Any] = field(default_factory=dict)
    # The trace this one was read on (kind, value), when it isn't the target: a link in a
    # profile's bio relates to that profile, not to the username that led to it. It must have
    # been yielded before (or be the target); otherwise the target stands in.
    via: tuple[EntityKind, str] | None = None


class ModuleError(Exception):
    """A failure the UI can explain. `code` is translated by the UI, with `params`."""

    retryable = True  # whether the user may retry the run

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


class RateLimited(ModuleError):
    """The source asks to wait: the run pauses until then and resumes from its checkpoint."""

    def __init__(self, retry_after: float, **params: Any) -> None:
        super().__init__("rate_limited", **params)
        self.retry_after = retry_after


class TransientError(ModuleError):
    """Worth retrying soon (network error, 5xx): the engine retries a few times by itself."""


class SourceUnavailable(ModuleError):
    """The source can't answer for now; the user may retry later."""


class InputRejected(ModuleError):
    """The source can't work with this input: retrying won't help."""

    retryable = False


class ModuleContext(Protocol):
    """What the engine gives a running module."""

    http: "HttpClient"
    log: logging.Logger
    attempt: int  # 1 for the first attempt
    checkpoint: dict[str, Any] | None  # what `save_checkpoint` last stored, if anything
    preferences: "Preferences"  # the user's settings for the sources (tokens, exclusions)

    async def save_checkpoint(self, data: dict[str, Any]) -> None:
        """Stores where the module is, so that a restart or a retry resumes from there."""

    async def progress(
        self, done: int, total: int | None, notes: dict[str, int] | None = None
    ) -> None:
        """Reports progress (shown live, used for the ETA), with counters worth showing
        ("checked", "unreachable"…): the run keeps the last ones as its report."""

    async def sleep(self, seconds: float) -> None:
        """Waits, honouring pause and the clock's speed. Also a pause point."""

    async def pause_point(self) -> None:
        """A pause point: returns at once unless the scan is paused."""


class SourceModule(ABC):
    meta: ClassVar[ModuleMeta]

    def accepts_target(self, kind: EntityKind, value: str) -> bool:
        """Whether a search makes sense for this seed. By default, any seed of an accepted kind,
        but a Fediverse handle (`name@instance`), which isn't a username elsewhere. A module that
        accepts account URLs narrows this to the sites it knows."""
        if kind == EntityKind.USERNAME and "@" in value:
            return False
        return kind in self.meta.accepts

    def allowed_hosts(
        self, preferences: "Preferences", target: Target | None = None
    ) -> tuple[str, ...]:
        """The hosts a run may contact: the declared ones, plus those the user added in the
        settings, for a module that lets them, or the target's own (a domain's site). Without a
        target: the hosts known in advance, for the Sources page."""
        return self.meta.hosts

    @abstractmethod
    def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        """Yields findings as they come. Each one is stored and shown before the next is asked."""
