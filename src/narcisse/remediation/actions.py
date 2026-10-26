"""What the user can do about a trace: the action sheet the trace's panel shows.

Pure functions over what is known of one trace (its kind, its sources, how it relates to the
others, where it was seen) and of the profile: each action names what to do, where (a page, an
address), how hard it is when the knowledge base says so, and which letter it can prepare.
Nothing is ever sent: the user follows the link or sends the letter themselves.
"""

from dataclasses import dataclass, field

from narcisse.domain import EntityKind, EntityStatus, ProfileKind
from narcisse.engine.scoring import (
    ARCHIVE_RELATIONS,
    PROFESSIONAL_PROFILES,
    REGISTRY_RELATIONS,
    REGISTRY_ROLES,
    SENSITIVE_LABELS,
    is_professional,
)
from narcisse.remediation.knowledge import Guide, Service, guide, host_of, service_for_url

# Relations that say a public commit or profile shows this address.
COMMIT_RELATIONS = frozenset({"commits_as", "shows_email"})
GRAVATAR = "https://gravatar.com/"
ARCHIVE = "https://web.archive.org/"


@dataclass(frozen=True, kw_only=True)
class TraceFacts:
    kind: EntityKind
    status: EntityStatus
    display: str
    normalized: str
    profile_kind: ProfileKind
    modules: frozenset[str]  # sources with a proof of it ("seed": declared, "manual": by hand)
    relations: frozenset[str]  # relations of the links that led to it
    evidence_urls: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class Action:
    code: str  # what to do (the UI explains it)
    service: Service | None = None
    url: str | None = None  # where to do it
    email: str | None = None  # whom to write to, when known
    letter: str | None = None  # the letter it can prepare (letters.py)
    links: tuple[Guide, ...] = field(default_factory=tuple)  # official pages that help


def _public(facts: TraceFacts) -> bool:
    return bool(facts.modules - {"seed"})


def _dereference() -> Action:
    return Action(
        code="dereference",
        letter="dereference",
        links=(
            guide("google_removal"),
            guide("bing_removal"),
            guide("qwant_removal"),
            guide("google_personal_info"),
        ),
    )


def _for_service(service: Service) -> Action:
    match service.category:
        case "broker":
            return Action(
                code="broker_opt_out",
                service=service,
                url=service.url,
                email=service.email,
                letter="objection",
            )
        case "business_directory":
            return Action(
                code="directory_objection",
                service=service,
                url=service.url,
                email=service.email,
                letter="objection",
                links=(guide("insee_diffusion"),),
            )
        case "archive":
            return Action(
                code="archive_removal",
                service=service,
                url=service.url,
                email=service.email,
                letter="archive",
            )
        case "keyserver":
            return Action(code="keyserver_hide", service=service, url=service.url)
    if service.difficulty == "impossible":
        return Action(
            code="cannot_delete",
            service=service,
            url=service.url,
            email=service.email,
            letter="erasure",
            links=(guide("cnil_find_contact"),),
        )
    return Action(
        code="delete_account",
        service=service,
        url=service.url,
        email=service.email,
        letter="account_deletion",
    )


def _ask_site(letter: str = "erasure") -> Action:
    return Action(code="ask_site", letter=letter, links=(guide("cnil_find_contact"),))


def _page(url: str, account: bool) -> list[Action]:
    service = service_for_url(url)
    if service is not None:
        return [_for_service(service)]
    if account:
        return [Action(code="delete_account_unknown", letter="account_deletion")]
    return [_ask_site()]


def _seen_on(facts: TraceFacts) -> list[Action]:
    """What to do on the sites that show this e-mail, phone or address: the brokers,
    directories, archive and key servers among them (not the accounts the pages belong to: an
    address in a GitHub commit doesn't call for deleting the account), and Gravatar's profile."""
    services: dict[str, Service] = {}
    for url in facts.evidence_urls:
        service = service_for_url(url)
        if service is not None and service.category != "account":
            services.setdefault(service.name, service)
    if "gravatar" in facts.modules and (gravatar := service_for_url(GRAVATAR)) is not None:
        services.setdefault(gravatar.name, gravatar)
    return [_for_service(s) for s in services.values()]


def actions_for(facts: TraceFacts) -> list[Action]:
    """The actions for this trace, the most useful first; none for a trace that isn't the
    user's or that nothing public shows."""
    if facts.kind == EntityKind.IDENTITY or facts.status == EntityStatus.FALSE_POSITIVE:
        return []
    if not _public(facts):
        return []

    actions: list[Action] = []
    if facts.profile_kind in PROFESSIONAL_PROFILES and is_professional(
        facts.kind, facts.modules, facts.relations
    ):
        actions.append(Action(code="keep_professional"))

    match facts.kind:
        case EntityKind.ACCOUNT | EntityKind.URL:
            actions += _page(facts.normalized, account=facts.kind == EntityKind.ACCOUNT)
            if host_of(facts.normalized) not in ("archive.org", "web.archive.org"):
                actions.append(_dereference())
        case EntityKind.LEAK:
            actions.append(Action(code="secure_leak"))
        case EntityKind.EMAIL:
            actions += _seen_on(facts)
            if facts.relations & COMMIT_RELATIONS:
                actions.append(Action(code="commit_email", links=(guide("github_commit_email"),)))
            if "certificate_email" in facts.relations:
                actions.append(Action(code="certificate_email"))
        case EntityKind.PHONE:
            actions.append(Action(code="phone_opposition", links=(guide("bloctel"),)))
            actions += _seen_on(facts)
        case EntityKind.DOMAIN:
            labels = facts.normalized.split(".")
            if len(labels) >= 3 and labels[0] in SENSITIVE_LABELS:
                actions.append(Action(code="restrict_subdomain"))
        case EntityKind.ADDRESS:
            if not facts.relations & REGISTRY_RELATIONS:
                actions += _seen_on(facts) or [_ask_site()]

    if facts.relations & REGISTRY_RELATIONS or "companies" in facts.modules:
        actions.append(Action(code="registry_diffusion", links=(guide("insee_diffusion"),)))
    if facts.relations & REGISTRY_ROLES:
        actions.append(Action(code="whois_privacy"))
    if (facts.relations & ARCHIVE_RELATIONS or "wayback" in facts.modules) and not any(
        a.code == "archive_removal" for a in actions
    ):
        archive = service_for_url(ARCHIVE)
        if archive is not None:
            actions.append(_for_service(archive))

    unique: list[Action] = []
    seen: set[tuple[str, str | None]] = set()
    for action in actions:
        key = (action.code, action.service.name if action.service else None)
        if key not in seen:
            seen.add(key)
            unique.append(action)
    return unique
