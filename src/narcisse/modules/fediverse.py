"""Mastodon and the Fediverse: a username's account on a list of large instances (and on the ones
the user adds), or a handle's (`name@instance`) on its own instance.

Mastodon's API finds a local account by its exact name. The links of a profile that Mastodon has
verified (the linked page links back with `rel="me"`) are held by the account's owner. Instances
that don't speak Mastodon's API are asked through WebFinger and ActivityPub.
"""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import quote, urlsplit

from narcisse.domain import EntityKind
from narcisse.engine.plugin import (
    Finding,
    InputRejected,
    ModuleContext,
    ModuleError,
    ModuleMeta,
    RateLimit,
    SourceModule,
    Target,
)
from narcisse.modules._text import html_text, is_profile, links, read_on_profiles, text_findings
from narcisse.notes import note

if TYPE_CHECKING:
    from narcisse.preferences import Preferences

# Large general instances, French-speaking ones and tech ones (checked on 2026-10-12).
INSTANCES = (
    "mastodon.social",
    "mastodon.online",
    "mstdn.social",
    "mas.to",
    "mastodon.world",
    "framapiaf.org",
    "mamot.fr",
    "piaille.fr",
    "mastodon.xyz",
    "social.tchncs.de",
    "chaos.social",
    "fosstodon.org",
    "infosec.exchange",
    "hachyderm.io",
    "toot.community",
)
ACTIVITY_JSON = "application/activity+json"
WEBFINGER_PROFILE_PAGE = "http://webfinger.net/rel/profile-page"


def _handle(value: str) -> tuple[str, str] | None:
    """(name, instance) for a handle `name@instance`."""
    name, at, host = value.removeprefix("@").partition("@")
    return (name, host.lower()) if at and name and "." in host else None


def _account_address(url: str) -> tuple[str, str] | None:
    """(name, instance) for a profile address `https://instance/@name`."""
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    if not parts.hostname or len(segments) != 1 or not segments[0].startswith("@"):
        return None
    name = segments[0][1:]
    return (name, parts.hostname) if name and "@" not in name else None


class Fediverse(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="fediverse",
        title={
            "fr": "Mastodon et Fediverse",
            "en": "Mastodon and the Fediverse",
        },
        description=(
            {
                "fr": (
                    "Le compte d’un pseudo sur une quinzaine de grandes instances Mastodon (et "
                    "celles ajoutées dans les réglages), ou d’un pseudo@instance sur son instance"
                    " : nom affiché, bio, liens du profil. Un lien vérifié par Mastodon "
                    "appartient au titulaire du compte."
                ),
                "en": (
                    "A username's account on about fifteen large Mastodon instances (and the ones"
                    " added in the settings), or a username@instance on its instance: display "
                    "name, bio, profile links. A link verified by Mastodon belongs to the "
                    "account's holder."
                ),
            }
        ),
        category="social",
        accepts=frozenset({EntityKind.USERNAME, EntityKind.ACCOUNT}),
        produces=frozenset({EntityKind.ACCOUNT, EntityKind.NAME, EntityKind.URL, EntityKind.EMAIL}),
        hosts=INSTANCES,
        rate_limit=RateLimit(requests=1, per_seconds=1),
        data_source="https://docs.joinmastodon.org/methods/accounts/#lookup",
    )

    def allowed_hosts(
        self, preferences: "Preferences", target: Target | None = None
    ) -> tuple[str, ...]:
        return tuple(dict.fromkeys(INSTANCES + preferences.fediverse_instances))

    def accepts_target(self, kind: EntityKind, value: str) -> bool:
        if kind == EntityKind.ACCOUNT:
            return _account_address(value) is not None
        return kind == EntityKind.USERNAME and ("@" not in value or _handle(value) is not None)

    def _places(self, ctx: ModuleContext, target: Target) -> list[tuple[str, str]]:
        """(instance, name) pairs to ask."""
        hosts = self.allowed_hosts(ctx.preferences)
        one = (
            _account_address(target.value)
            if target.kind == EntityKind.ACCOUNT
            else _handle(target.value)
        )
        if one is None:
            return [(host, target.value) for host in hosts]
        name, host = one
        if host not in hosts:
            # Only the instances the user knows about are contacted (they can add this one).
            raise InputRejected("instance_not_listed", host=host)
        return [(host, name)]

    def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        return read_on_profiles(self._run(ctx, target))

    async def _run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        places = self._places(ctx, target)
        notes: dict[str, int] = {"checked": 0, "found": 0, "unreachable": 0}
        for done, (host, name) in enumerate(places):
            await ctx.progress(done, len(places), notes)
            try:
                account = await self._lookup(ctx, host, name)
            except ModuleError:
                notes["unreachable"] += 1
                continue
            notes["checked"] += 1
            if account is None:
                continue
            notes["found"] += 1
            for finding in self._findings(target, host, name, account):
                yield finding
        await ctx.progress(len(places), len(places), notes)

    async def _lookup(self, ctx: ModuleContext, host: str, name: str) -> dict[str, Any] | None:
        """The account, in the shape of Mastodon's API, or None if there's none."""
        response = await ctx.http.get(f"https://{host}/api/v1/accounts/lookup?acct={quote(name)}")
        if response.status_code == 404:
            return None
        if response.status_code == 200 and "json" in response.headers.get("content-type", ""):
            account: dict[str, Any] = response.json()
            return account
        return await self._activitypub(ctx, host, name)

    async def _activitypub(self, ctx: ModuleContext, host: str, name: str) -> dict[str, Any] | None:
        """For instances without Mastodon's API (or closed to anonymous clients): WebFinger, then
        the ActivityPub actor, put in the shape of Mastodon's API."""
        response = await ctx.http.get(
            f"https://{host}/.well-known/webfinger?resource=acct:{quote(name)}@{host}"
        )
        if response.status_code >= 400:
            return None
        entries = (response.json() or {}).get("links") or []
        page = next(
            (e.get("href") for e in entries if e.get("rel") == WEBFINGER_PROFILE_PAGE), None
        )
        actor_url = next(
            (
                e.get("href")
                for e in entries
                if e.get("rel") == "self" and "activity" in str(e.get("type"))
            ),
            None,
        )
        account: dict[str, Any] = {"url": page}
        if actor_url and urlsplit(actor_url).hostname == host:
            actor = await ctx.http.get(actor_url, headers={"Accept": ACTIVITY_JSON})
            if actor.status_code == 200:
                data: dict[str, Any] = actor.json()
                account.update(
                    display_name=data.get("name"),
                    note=data.get("summary"),
                    created_at=data.get("published"),
                    fields=[
                        {"name": a.get("name"), "value": a.get("value")}
                        for a in data.get("attachment") or []
                        if a.get("type") == "PropertyValue"
                    ],
                )
        return account

    def _findings(
        self, target: Target, host: str, name: str, account: dict[str, Any]
    ) -> list[Finding]:
        handle = f"{name}@{host}"
        # The address WhatsMyName gives too, so that both findings make one trace.
        url = f"https://{host}/@{name}"
        found: list[Finding] = []
        if target.kind != EntityKind.ACCOUNT:
            found.append(
                Finding(
                    kind=EntityKind.ACCOUNT,
                    value=url,
                    relation="has_account",
                    # A handle given by the user is theirs; the same name elsewhere may not be.
                    confidence=0.9 if "@" in target.value else 0.5,
                    url=url,
                    note=note("fediverse_account", handle=handle, host=host),
                    attributes={
                        "site": f"Fediverse ({host})",
                        **(
                            {"created": str(account["created_at"])[:10]}
                            if account.get("created_at")
                            else {}
                        ),
                        **({"bio": html_text(account["note"])} if account.get("note") else {}),
                        **({"bot": True} if account.get("bot") else {}),
                    },
                )
            )
        if account.get("display_name"):
            found.append(
                Finding(
                    kind=EntityKind.NAME,
                    value=account["display_name"],
                    relation="shows_name",
                    confidence=0.5,
                    url=url,
                    note=note("fediverse_name", handle=handle),
                )
            )
        found += text_findings(
            account.get("note") or "",
            html=True,
            url=url,
            where=note("in_fediverse_bio", handle=handle),
            confidence=0.6,
        )
        for field in account.get("fields") or []:
            found += self._field(handle, url, field)
        moved = (account.get("moved") or {}).get("url")
        if moved:
            found.append(
                Finding(
                    kind=EntityKind.ACCOUNT,
                    value=moved,
                    relation="links_to",
                    confidence=0.8,
                    url=url,
                    note=note("fediverse_moved", handle=handle),
                )
            )
        return found

    def _field(self, handle: str, url: str, field: dict[str, Any]) -> list[Finding]:
        label = html_text(str(field.get("name") or "")) or "?"
        value = str(field.get("value") or "")
        if not field.get("verified_at"):
            return list(
                text_findings(
                    value,
                    html=True,
                    url=url,
                    where=note("in_fediverse_field", handle=handle, label=label),
                    confidence=0.6,
                )
            )
        return [
            Finding(
                kind=EntityKind.ACCOUNT if is_profile(link) else EntityKind.URL,
                value=link,
                relation="links_to",
                confidence=0.9,
                url=url,
                note=note("fediverse_verified_link", handle=handle, label=label),
            )
            for link in links(value, html=True)
        ]
