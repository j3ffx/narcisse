"""What Narcisse knows about getting a trace removed, site by site.

Two sources, both versioned in `data/`: a copy of JustDeleteMe's list of account deletion pages
(MIT, refreshed by `scripts/update-jdm.py`), and Narcisse's own sheets (`guides.json`): data
brokers, business directories, the archive, key servers, and the official pages the action
sheets link to (search engines' removal forms, the CNIL, the INSEE…), checked on the date the
file gives. Narcisse's own sheets win over JustDeleteMe for a host both know.
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

DATA = Path(__file__).parent / "data"

Category = Literal["account", "archive", "keyserver", "broker", "business_directory"]
Difficulty = Literal["easy", "medium", "hard", "limited", "impossible"]


@dataclass(frozen=True, kw_only=True)
class Service:
    name: str
    category: Category
    domains: tuple[str, ...]
    url: str | None = None
    difficulty: Difficulty | None = None
    notes: str | None = None
    notes_lang: Literal["fr", "en"] = "fr"
    email: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    source: Literal["jdm", "narcisse"] = "narcisse"


@dataclass(frozen=True, kw_only=True)
class Guide:
    """An official page an action sheet points to."""

    title: str
    url: str


def _jdm(site: dict[str, Any]) -> Service:
    # Prefer the French page and notes when the list has them.
    notes_fr = site.get("notes_fr")
    return Service(
        name=site["name"],
        category="account",
        domains=tuple(site["domains"]),
        url=site.get("url_fr") or site.get("url"),
        difficulty=site.get("difficulty"),
        notes=notes_fr or site.get("notes"),
        notes_lang="fr" if notes_fr else "en",
        email=site.get("email"),
        email_subject=site.get("email_subject"),
        email_body=site.get("email_body"),
        source="jdm",
    )


@cache
def _guides() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((DATA / "guides.json").read_text(encoding="utf-8"))
    return data


@cache
def _by_domain() -> dict[str, Service]:
    sites = json.loads((DATA / "jdm-sites.json").read_text(encoding="utf-8"))
    index: dict[str, Service] = {}
    for site in sites:
        service = _jdm(site)
        for domain in service.domains:
            index.setdefault(domain.lower().removeprefix("www."), service)
    for item in _guides()["services"]:
        service = Service(
            name=item["name"],
            category=item["category"],
            domains=tuple(item["domains"]),
            url=item.get("url"),
            difficulty=item.get("difficulty"),
            notes=item.get("notes"),
            email=item.get("email"),
        )
        for domain in service.domains:
            index[domain] = service
    return index


def guide(key: str) -> Guide:
    item = _guides()["links"][key]
    return Guide(title=item["title"], url=item["url"])


def host_of(url: str) -> str | None:
    """The host of a page, without `www.`; None when it isn't a web address."""
    try:
        host = urlsplit(url.strip()).hostname
    except ValueError:
        return None
    return host.removeprefix("www.") if host else None


def service_for_host(host: str) -> Service | None:
    """The service a host belongs to: the host itself, or the closest parent domain known."""
    index = _by_domain()
    labels = host.lower().removeprefix("www.").rstrip(".").split(".")
    for start in range(len(labels) - 1):
        if service := index.get(".".join(labels[start:])):
            return service
    return None


def service_for_url(url: str) -> Service | None:
    host = host_of(url)
    return service_for_host(host) if host else None


def is_broker(url: str) -> Service | None:
    service = service_for_url(url)
    return service if service is not None and service.category == "broker" else None
