"""How sure Narcisse is that a trace is the user's (confidence), and how much it exposes them
(risk).

Pure functions over what is known of one trace and its links: every rule that applies leaves a
`Reason` (a code the UI translates, the points it adds or the factor it applies), so that the UI
can say why a score is what it is. Scores are 0..1 in storage and shown as 0–100.

Confidence ("is it me?"): the sources' own confidence, more when several independent sources found
it or when it ties traces the user declared or confirmed together, much less when it was only
reached through traces the user rejected. The user's word ends the question: 100 or 0.

Risk ("how much does it expose me?"): a base per kind of trace (a postal address exposes more
than a username), points for what it reveals (passwords in a leak, a birth date in a register, an
adult site, a data broker…), weighted by confidence: a trace that may not be the user's counts
less. Nothing found in public is no exposure, and neither is a trace the user rejected.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from narcisse.domain import EntityKind, EntityStatus


@dataclass(frozen=True)
class Neighbour:
    """The other end of a link, as far as scoring cares."""

    kind: EntityKind
    status: EntityStatus
    declared: bool
    display: str


@dataclass(frozen=True)
class Link:
    relation: str
    module: str
    other: Neighbour
    incoming: bool  # True: the other trace led to this one


@dataclass(frozen=True)
class Trace:
    kind: EntityKind
    status: EntityStatus
    declared: bool  # one of the profile's elements
    normalized: str
    module_confidence: float | None  # the highest any source gave, 0..1
    modules: frozenset[str]  # the sources with a proof of it ("manual": the user added it)
    attributes: Mapping[str, Any] = field(default_factory=dict)
    links: tuple[Link, ...] = ()


@dataclass(frozen=True)
class Reason:
    code: str
    points: int | None = None  # points added (or removed), or the value set, on a 0–100 scale
    factor: float | None = None  # what the score was multiplied by
    params: Mapping[str, Any] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code}
        if self.points is not None:
            out["points"] = self.points
        if self.factor is not None:
            out["factor"] = self.factor
        if self.params:
            out["params"] = dict(self.params)
        return out


@dataclass(frozen=True)
class Scores:
    confidence: float
    risk: float
    confidence_reasons: tuple[Reason, ...]
    risk_reasons: tuple[Reason, ...]

    def reasons_json(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "confidence": [r.as_json() for r in self.confidence_reasons],
            "risk": [r.as_json() for r in self.risk_reasons],
        }


# Confidence

DEFAULT_SOURCE_CONFIDENCE = 50  # a source that gave none
SEVERAL_SOURCES = {2: 10, 3: 15}  # independent sources → points (3 and more: 15)
CORROBORATED = 15  # linked to two or more traces the user declared or confirmed
VIA_CONFIRMED = 10  # found from a trace the user confirmed
VIA_REJECTED = 0.3  # only ever reached through traces the user rejected
UNREVIEWED_CAP = 95  # only the user's word makes it certain

# Risk

BASE_RISK = {
    EntityKind.ADDRESS: 70,
    EntityKind.PHONE: 60,
    EntityKind.LEAK: 50,
    EntityKind.PHOTO: 40,
    EntityKind.EMAIL: 30,
    EntityKind.ACCOUNT: 20,
    EntityKind.URL: 20,
    EntityKind.DOMAIN: 15,
    EntityKind.ORGANIZATION: 15,
    EntityKind.NAME: 10,
    EntityKind.USERNAME: 10,
    EntityKind.IDENTITY: 0,
}
LEAKED_PASSWORDS = 30
LEAKED_IDENTITY = 30
BIRTH_PUBLISHED = 30
ADULT_SITE = 40
DATA_BROKER = 30
MOVEMENTS = 20
SENSITIVE_SUBDOMAIN = 25
REGISTRY_CONTACT = 20
ARCHIVED = 10

# Passwords readable from the leak (XposedOrNot's password risk).
READABLE_PASSWORDS = frozenset({"plaintext", "easytocrack"})
# What a leak may hold that identifies someone or opens their money (as `xposedornot` writes it).
IDENTITY_DATA = frozenset(
    {
        "pièces d’identité",
        "pièces d’identité partielles",
        "numéros de passeport",
        "numéros de sécurité sociale",
        "cartes bancaires",
        "données partielles de cartes bancaires",
        "numéros de compte bancaire",
    }
)
DATA_BROKERS = frozenset({"rocketreach"})
# Sources whose accounts show where someone goes.
MOVEMENT_SITES = ("strava.com",)
# Subdomains that name a door into someone's machines or files.
SENSITIVE_LABELS = frozenset(
    {
        "nas",
        "vpn",
        "admin",
        "backup",
        "backups",
        "cloud",
        "nextcloud",
        "owncloud",
        "files",
        "remote",
        "intranet",
        "router",
        "camera",
        "cam",
        "home",
        "homeassistant",
        "grafana",
        "git",
        "jenkins",
        "staging",
        "dev",
        "webmail",
    }
)
REGISTRY_ROLES = frozenset({"registrant", "administrative_contact", "technical_contact"})
ARCHIVE_RELATIONS = frozenset({"archived_at", "archived_page"})

# Risk levels, on the 0..1 scale.
LEVELS = ((0.75, "critical"), (0.5, "high"), (0.25, "medium"), (0.0, "low"))


def risk_level(risk: float) -> str:
    for floor, level in LEVELS:
        if risk >= floor:
            return level
    return "low"


def _clamp(points: float) -> int:
    return round(min(100.0, max(0.0, points)))


def confidence(trace: Trace) -> tuple[int, tuple[Reason, ...]]:
    """0–100, and why."""
    if trace.kind == EntityKind.IDENTITY:
        return 100, (Reason("identity", points=100),)
    if trace.declared:
        return 100, (Reason("declared", points=100),)
    if trace.status == EntityStatus.CONFIRMED:
        return 100, (Reason("confirmed", points=100),)
    if trace.status == EntityStatus.FALSE_POSITIVE:
        return 0, (Reason("rejected", points=0),)

    reasons: list[Reason] = []
    if trace.module_confidence is None:
        points = float(DEFAULT_SOURCE_CONFIDENCE)
        reasons.append(Reason("no_source_confidence", points=DEFAULT_SOURCE_CONFIDENCE))
    else:
        points = trace.module_confidence * 100
        reasons.append(Reason("sources", points=_clamp(points)))

    independent = len(trace.modules - {"manual"})
    if independent >= 2:
        bonus = SEVERAL_SOURCES.get(independent, max(SEVERAL_SOURCES.values()))
        points += bonus
        reasons.append(Reason("several_sources", points=bonus, params={"count": independent}))

    anchors = {
        (link.other.kind, link.other.display)
        for link in trace.links
        if link.other.kind != EntityKind.IDENTITY
        and (link.other.declared or link.other.status == EntityStatus.CONFIRMED)
    }
    via_confirmed = [
        link.other.display
        for link in trace.links
        if link.incoming
        and not link.other.declared
        and link.other.kind != EntityKind.IDENTITY
        and link.other.status == EntityStatus.CONFIRMED
    ]
    if len(anchors) >= 2:
        points += CORROBORATED
        reasons.append(Reason("corroborated", points=CORROBORATED, params={"count": len(anchors)}))
    elif via_confirmed:
        points += VIA_CONFIRMED
        reasons.append(
            Reason("via_confirmed", points=VIA_CONFIRMED, params={"trace": via_confirmed[0]})
        )

    sources = [
        link.other
        for link in trace.links
        if link.incoming and link.other.kind != EntityKind.IDENTITY
    ]
    if sources and all(s.status == EntityStatus.FALSE_POSITIVE for s in sources):
        points *= VIA_REJECTED
        reasons.append(Reason("via_rejected", factor=VIA_REJECTED))

    if points > UNREVIEWED_CAP:
        points = UNREVIEWED_CAP
        reasons.append(Reason("unreviewed_cap", points=UNREVIEWED_CAP))
    return _clamp(points), tuple(reasons)


def _first_label(normalized: str) -> str | None:
    labels = normalized.split(".")
    return labels[0] if len(labels) >= 3 else None


def risk(trace: Trace, confidence_points: int) -> tuple[int, tuple[Reason, ...]]:
    """0–100, and why. `confidence_points` is the trace's confidence (see `confidence`)."""
    if trace.kind == EntityKind.IDENTITY:
        return 0, (Reason("identity_risk", points=0),)
    if trace.status == EntityStatus.FALSE_POSITIVE:
        return 0, (Reason("rejected", points=0),)
    if not trace.modules:
        # Declared, never found anywhere public: nothing exposes it (yet).
        return 0, (Reason("not_public", points=0),)

    base = BASE_RISK.get(trace.kind, 10)
    points = float(base)
    reasons = [Reason("kind", points=base, params={"kind": str(trace.kind)})]

    def add(code: str, value: int, **params: Any) -> None:
        nonlocal points
        points += value
        reasons.append(Reason(code, points=value, params=params))

    attributes = trace.attributes
    if trace.kind == EntityKind.LEAK:
        data = {str(item) for item in attributes.get("data") or []}
        if "mots de passe" in data and attributes.get("password_risk") in READABLE_PASSWORDS:
            add("leaked_passwords", LEAKED_PASSWORDS)
        if data & IDENTITY_DATA:
            add("leaked_identity", LEAKED_IDENTITY)
    if attributes.get("birth"):
        add("birth_published", BIRTH_PUBLISHED)
    if attributes.get("adult") is True:
        add("adult_site", ADULT_SITE)
    if broker := sorted(trace.modules & DATA_BROKERS):
        add("data_broker", DATA_BROKER, source=broker[0])
    if trace.kind == EntityKind.ACCOUNT and any(s in trace.normalized for s in MOVEMENT_SITES):
        add("movements", MOVEMENTS)
    label = _first_label(trace.normalized) if trace.kind == EntityKind.DOMAIN else None
    if label in SENSITIVE_LABELS:
        add("sensitive_subdomain", SENSITIVE_SUBDOMAIN, label=label)
    if any(link.incoming and link.relation in REGISTRY_ROLES for link in trace.links):
        add("registry_contact", REGISTRY_CONTACT)
    if any(link.incoming and link.relation in ARCHIVE_RELATIONS for link in trace.links):
        add("archived", ARCHIVED)

    exposure = min(100.0, points)
    weight = 0.5 + 0.5 * confidence_points / 100
    if weight < 1:
        reasons.append(Reason("weighted", factor=round(weight, 2)))
    return _clamp(exposure * weight), tuple(reasons)


def score(trace: Trace) -> Scores:
    confidence_points, confidence_reasons = confidence(trace)
    risk_points, risk_reasons = risk(trace, confidence_points)
    return Scores(
        confidence=confidence_points / 100,
        risk=risk_points / 100,
        confidence_reasons=confidence_reasons,
        risk_reasons=risk_reasons,
    )
