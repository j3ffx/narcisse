"""A domain's registration: who holds it, with whom, since when, and whether the registry shows
the holder's details or hides them.

RDAP first (the registry's server, from IANA's bootstrap file, then the registrar's when the
registry points to it); WHOIS (port 43) for the top-level domains without RDAP. Registries hide
an individual's details more and more: when they do, that is the good news this module reports.

Data: IANA (RDAP bootstrap, registrar IDs, WHOIS servers); copy in `data/registries.json`,
refreshed by `scripts/update-registries.py`.
"""

import json
import re
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlsplit

from narcisse.domain import EntityKind
from narcisse.engine.plugin import (
    Finding,
    InputRejected,
    ModuleContext,
    ModuleMeta,
    RateLimit,
    SourceModule,
    SourceUnavailable,
    Target,
)
from narcisse.notes import note

DATA = json.loads((Path(__file__).parent / "data" / "registries.json").read_text("utf-8"))
RDAP: dict[str, str] = DATA["rdap"]
REGISTRARS: frozenset[str] = frozenset(DATA["registrars"])
WHOIS: dict[str, str] = DATA["whois"]
HOSTS = tuple(
    sorted(
        {urlsplit(url).hostname or "" for url in RDAP.values()} | REGISTRARS | set(WHOIS.values())
    )
)
RDAP_JSON = "application/rdap+json"

# What registries and registrars write instead of a detail they hide.
_HIDDEN = re.compile(
    r"redact|privacy|private|protect|not ?disclosed|withheld|masked|hidden|gdpr|"
    r"non[- ]?public|not shown|whoisguard|domains? by proxy|contact[- ]?privacy|obfuscat|"
    r"not available|please query|données personnelles",
    re.IGNORECASE,
)
# The registrant's details behind a proxy: an address of the proxy, not the holder's.
_PROXY_EMAIL = re.compile(
    r"privacy|proxy|protect|whoisguard|withheld|redact|anonym|obfuscat|contact-form|"
    r"gdpr-masking|abuse",
    re.IGNORECASE,
)
_UNREGISTERED = re.compile(
    r"^(no match|not found|no entries found|no data found|domain not found"
    r"|status:\s*(free|available))|is available for registration|no object found",
    re.IGNORECASE | re.MULTILINE,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.IGNORECASE)

ROLES = {
    "registrant": ("registrant", "titulaire", 0.6),
    "administrative": ("administrative_contact", "contact administratif", 0.5),
    "technical": ("technical_contact", "contact technique", 0.4),
}


@dataclass
class Record:
    """What a registration says, whatever the protocol."""

    registrar: str | None = None
    created: str | None = None
    expires: str | None = None
    # Each detail shown, in order, with the roles it is given (holder, technical contact…).
    contacts: dict[tuple[EntityKind, str], list[str]] = field(default_factory=dict)
    hidden: int = 0  # details the registry hides


def _visible(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if value and not _HIDDEN.search(value) else None


def _phone(value: str) -> str:
    return value.removeprefix("tel:").split(";")[0].strip()


def _day(value: str | None) -> str | None:
    return value[:10] if value and re.match(r"\d{4}-\d\d-\d\d", value) else value


# RDAP


def _vcard(entity: dict[str, Any]) -> dict[str, list[Any]]:
    """A jCard's properties by name: name → [value, …] (the `label` of an address included)."""
    found: dict[str, list[Any]] = {}
    array = entity.get("vcardArray")
    if not (isinstance(array, list) and len(array) == 2 and isinstance(array[1], list)):
        return found
    for prop in array[1]:
        if not (isinstance(prop, list) and len(prop) >= 4):
            continue
        name, params, value = prop[0], prop[1], prop[3]
        kinds = params.get("type", []) if isinstance(params, dict) else []
        if name == "tel" and "fax" in (kinds if isinstance(kinds, list) else [kinds]):
            continue
        if name == "adr" and isinstance(params, dict) and params.get("label"):
            value = params["label"]
        found.setdefault(name, []).append(value)
    return found


def _address(value: Any) -> str | None:
    if isinstance(value, list):
        parts = [p if isinstance(p, str) else " ".join(map(str, p)) for p in value]
        value = ", ".join(p.strip() for p in parts if p and p.strip())
    return _visible(value if isinstance(value, str) else None)


def _entities(data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for entity in data.get("entities") or []:
        if isinstance(entity, dict):
            yield entity
            yield from _entities(entity)


def read_rdap(data: dict[str, Any], record: Record) -> None:
    """Adds what an RDAP domain answer says to `record` (the registry's, then the registrar's)."""
    for event in data.get("events") or []:
        action, date = event.get("eventAction"), _day(event.get("eventDate"))
        if action == "registration":
            record.created = record.created or date
        elif action == "expiration":
            record.expires = record.expires or date
    for entity in _entities(data):
        roles = set(entity.get("roles") or [])
        card = _vcard(entity)
        if "registrar" in roles:
            record.registrar = record.registrar or next(iter(card.get("fn") or []), None)
            continue
        for role in ROLES:
            if role not in roles:
                continue
            fields: list[tuple[EntityKind, Any]] = [
                *((EntityKind.NAME, v) for v in card.get("fn") or []),
                *((EntityKind.ORGANIZATION, v) for v in card.get("org") or []),
                *((EntityKind.EMAIL, v) for v in card.get("email") or []),
                *((EntityKind.PHONE, v) for v in card.get("tel") or []),
                *((EntityKind.ADDRESS, v) for v in card.get("adr") or []),
            ]
            if not card or not fields:
                record.hidden += 1  # an entity with no card: withheld (RFC 9537)
            for kind, raw in fields:
                _add(record, role, kind, raw)


def _add(record: Record, role: str, kind: EntityKind, raw: Any) -> None:
    if kind == EntityKind.ADDRESS:
        value = _address(raw)
    elif isinstance(raw, list):
        value = _visible(" ".join(str(v) for v in raw if v))
    else:
        value = _visible(str(raw) if raw is not None else None)
    if value and kind == EntityKind.PHONE:
        value = _phone(value)
    if value and kind == EntityKind.EMAIL and _PROXY_EMAIL.search(value):
        value = None
    if value and kind == EntityKind.NAME and value == record.registrar:
        value = None
    if value is None:
        record.hidden += 1
    elif role not in (roles := record.contacts.setdefault((kind, value), [])):
        roles.append(role)


def registrar_link(data: dict[str, Any]) -> str | None:
    """The registrar's own RDAP record of the domain, when the registry points to it."""
    for link in data.get("links") or []:
        href = link.get("href") or ""
        if (
            link.get("rel") == "related"
            and RDAP_JSON in (link.get("type") or "")
            and "/domain/" in href
            and urlsplit(href).hostname in REGISTRARS
        ):
            return str(href)
    return None


# WHOIS

_KEY = re.compile(r"^\s*([^:\n]{2,60}?)\s*:\s*(.*)$")
_SECTION_ROLES = (
    ("registrant", ("registrant", "holder", "owner", "titulaire")),
    ("administrative", ("admin",)),
    ("technical", ("tech",)),
)


_OTHER_PARTY = ("registrar", "abuse", "reseller")
_POINTER = re.compile(r"https?://|www\.|\bvisit\b|\bsee\b", re.IGNORECASE)
_CREATED = ("creation date", "created", "registered on", "registration date")
_EXPIRES = ("expiry date", "expiration date", "expire", "paid-till")


def _other_party(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in _OTHER_PARTY)


def _role_of(text: str) -> str | None:
    """The contact a key or a section title is about, if it is one of the holder's."""
    if _other_party(text):
        return None
    lowered = text.lower()
    for role, words in _SECTION_ROLES:
        if any(word in lowered for word in words):
            return role
    return None


def _section_title(line: str, match: re.Match[str] | None) -> str | None:
    """`Registrant:` or `Registrant` alone on an unindented line opens a section."""
    if line[:1].isspace():
        return None
    if match is not None:
        return match.group(1) if not match.group(2).strip() else None
    return line.strip() if len(line.strip()) <= 40 else None


def read_whois(text: str, record: Record) -> None:
    """Adds what a WHOIS answer says to `record`. Formats differ by registry: details are read
    as `Registrant Name: …` lines or within a `Registrant:` section."""
    section = ""
    section_role: str | None = None
    for line in text.splitlines():
        if not line.strip():
            section, section_role = "", None
            continue
        if line.lstrip().startswith(("%", "#", ">>>")):
            continue
        match = _KEY.match(line)
        if (title := _section_title(line, match)) is not None:
            section, section_role = title, _role_of(title)
            continue
        if match:
            key, value = match.group(1).strip(), match.group(2).strip()
        elif section:
            key, value = "", line.strip()  # a value alone in its section (.eu, .be)
            if _POINTER.search(value) and not _HIDDEN.search(value):
                continue
        else:
            continue
        if not value:
            continue
        lowered = key.lower()
        if "registrar" in section.lower() and lowered in ("", "name", "organisation"):
            record.registrar = record.registrar or _visible(value)
            continue
        if lowered in ("registrar", "registrar name", "sponsoring registrar"):
            record.registrar = record.registrar or _visible(value)
            continue
        if any(w in lowered for w in _CREATED):
            record.created = record.created or _day(value)
            continue
        if any(w in lowered for w in _EXPIRES):
            record.expires = record.expires or _day(value)
            continue
        if _other_party(key):
            continue
        role = _role_of(key) or section_role
        kind = _kind_of(lowered, value) if role is not None else None
        if role is not None and kind is not None:
            _add(record, role, kind, value)


def _kind_of(key: str, value: str) -> EntityKind | None:
    if "mail" in key or (not key and _EMAIL.fullmatch(value)):
        return EntityKind.EMAIL
    if "phone" in key or "fax" in key or "tel" in key:
        return None if "fax" in key else EntityKind.PHONE
    if "organi" in key or key.endswith(" org"):
        return EntityKind.ORGANIZATION
    if any(w in key for w in ("street", "address", "city", "postal", "country", "state")):
        return None  # pieces of an address: too scattered to make one reliably
    if key in ("", "name") or key.endswith(" name") or key in ("registrant", "holder"):
        return EntityKind.NAME
    return None


class Registration(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="registration",
        title={
            "fr": "Enregistrement du domaine (RDAP, WHOIS)",
            "en": "Domain registration (RDAP, WHOIS)",
        },
        description=(
            {
                "fr": (
                    "Qui détient un domaine et chez qui (RDAP, ou WHOIS pour les extensions qui "
                    "n’ont pas RDAP) : nom, email, téléphone, adresse du titulaire quand le "
                    "registre les publie, ou le fait qu’il les masque."
                ),
                "en": (
                    "Who holds a domain and with whom (RDAP, or WHOIS for the extensions without "
                    "RDAP): the holder's name, email, phone and address when the registry "
                    "publishes them, or the fact that it hides them."
                ),
            }
        ),
        category="domains",
        accepts=frozenset({EntityKind.DOMAIN}),
        produces=frozenset(
            {
                EntityKind.ORGANIZATION,
                EntityKind.NAME,
                EntityKind.EMAIL,
                EntityKind.PHONE,
                EntityKind.ADDRESS,
            }
        ),
        hosts=HOSTS,
        rate_limit=RateLimit(requests=1, per_seconds=2),
        max_parallel_runs=2,
        data_source="https://www.iana.org/domains/root/db",
    )

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        labels = target.normalized.split(".")
        tld = labels[-1]
        if tld not in RDAP and tld not in WHOIS:
            raise InputRejected("no_registry", tld=tld)
        # The name itself, then its parents (a subdomain isn't registered on its own).
        names = [".".join(labels[i:]) for i in range(len(labels) - 1)]
        await ctx.progress(0, None)
        for name in names:
            record, url = await self._lookup(ctx, name)
            if record is None:
                continue
            for finding in self._findings(target, name, record, url):
                yield finding
            await ctx.progress(1, 1, {"published": len(record.contacts), "redacted": record.hidden})
            return
        await ctx.progress(1, 1, {"unregistered": 1})

    async def _lookup(self, ctx: ModuleContext, name: str) -> tuple[Record | None, str | None]:
        """The registration of `name`, and the address it was read at (RDAP), or None when the
        name isn't registered."""
        record = Record()
        tld = name.rsplit(".", 1)[-1]
        if tld not in RDAP:
            text = await ctx.http.whois(WHOIS[tld], name)
            if _UNREGISTERED.search(text):
                return None, None
            read_whois(text, record)
            return record, None
        url = f"{RDAP[tld]}domain/{name}"
        data = await self._rdap(ctx, url)
        if data is None:
            return None, None
        read_rdap(data, record)
        if link := registrar_link(data):
            # The registrar's record is a complement: when it can't be read, the registry's stands.
            try:
                more = await self._rdap(ctx, link)
            except SourceUnavailable:
                more = None
            if more:
                read_rdap(more, record)
        return record, url

    async def _rdap(self, ctx: ModuleContext, url: str) -> dict[str, Any] | None:
        response = await ctx.http.get(url, headers={"Accept": f"{RDAP_JSON}, application/json"})
        # 404, and 400 ("bad request"), both mean the registry won't register this name: a free
        # domain, or a subdomain of a public suffix (nuagerie.pages.dev under pages.dev). The run
        # then climbs to the parent instead of failing. Rate limits and 5xx are caught upstream.
        if response.status_code in (400, 404):
            return None
        host = urlsplit(url).hostname
        if response.status_code >= 400:
            raise SourceUnavailable("source_refused", host=host, status=response.status_code)
        try:
            data = response.json()
        except ValueError as exc:
            raise SourceUnavailable("source_refused", host=host) from exc
        return data if isinstance(data, dict) else None

    def _findings(
        self, target: Target, name: str, record: Record, url: str | None
    ) -> Iterator[Finding]:
        parent = name != target.normalized
        child = target.normalized if parent else None
        shown = "shown" if record.contacts else "hidden" if record.hidden else "absent"
        if record.registrar:
            yield Finding(
                kind=EntityKind.ORGANIZATION,
                value=record.registrar,
                relation="registered_with",
                confidence=0.9,
                url=url,
                note=note(
                    "registered_with",
                    domain=name,
                    child=child,
                    registrar=record.registrar,
                    created=record.created,
                    expires=record.expires,
                    contacts=shown,
                ),
                attributes={
                    k: v for k, v in (("created", record.created), ("expires", record.expires)) if v
                },
            )
        for (kind, value), roles in record.contacts.items():
            relation, _, confidence = ROLES[roles[0]]
            yield Finding(
                kind=kind,
                value=value,
                relation=relation,
                # Details of a parent domain (a hosting service's) are seldom the user's.
                confidence=0.2 if parent else confidence,
                url=url,
                note=note("registry_contact", roles=list(roles), domain=name, child=child),
            )
