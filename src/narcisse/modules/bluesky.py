"""Bluesky: the public profile behind a handle (a username on bsky.social, or a domain name).

A handle that is a domain name is checked by Bluesky itself (DNS or a file on the site): the
domain and the account are then held by the same person. The public AppView answers without an
account.
"""

from collections.abc import AsyncIterator
from typing import Any, ClassVar
from urllib.parse import urlsplit

from narcisse.domain import EntityKind
from narcisse.engine.plugin import (
    Finding,
    ModuleContext,
    ModuleMeta,
    RateLimit,
    SourceModule,
    SourceUnavailable,
    Target,
)
from narcisse.modules._text import text_findings

API = "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile"
DEFAULT_DOMAIN = "bsky.social"
# What Bluesky shows when a domain handle no longer points at its account.
INVALID_HANDLE = "handle.invalid"


def _profile_handle(url: str) -> str | None:
    """The handle in a `https://bsky.app/profile/<handle>` address."""
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    if parts.hostname not in ("bsky.app", "www.bsky.app") or len(segments) != 2:
        return None
    return segments[1] if segments[0] == "profile" else None


def handle_for(target: Target) -> str | None:
    """The handle to ask for, spelled as the user wrote it."""
    match target.kind:
        case EntityKind.USERNAME:
            return target.value if "." in target.value else f"{target.value}.{DEFAULT_DOMAIN}"
        case EntityKind.DOMAIN:
            return target.normalized
        case EntityKind.ACCOUNT:
            return _profile_handle(target.value)
    return None


class Bluesky(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="bluesky",
        title="Bluesky",
        description=(
            "Le profil Bluesky d’un pseudo (pseudo.bsky.social) ou d’un domaine utilisé comme "
            "pseudo : nom affiché, description et les liens qu’elle contient. Un domaine servant "
            "de pseudo est vérifié par Bluesky : le compte et le domaine ont le même titulaire."
        ),
        category="social",
        accepts=frozenset({EntityKind.USERNAME, EntityKind.DOMAIN, EntityKind.ACCOUNT}),
        produces=frozenset(
            {
                EntityKind.ACCOUNT,
                EntityKind.NAME,
                EntityKind.URL,
                EntityKind.EMAIL,
                EntityKind.DOMAIN,
            }
        ),
        hosts=("public.api.bsky.app",),
        rate_limit=RateLimit(requests=1, per_seconds=1),
        data_source="https://docs.bsky.app/docs/api/app-bsky-actor-get-profile",
    )

    def accepts_target(self, kind: EntityKind, value: str) -> bool:
        if kind == EntityKind.ACCOUNT:
            return _profile_handle(value) is not None
        return super().accepts_target(kind, value)

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        asked = handle_for(target)
        if asked is None:
            return
        await ctx.progress(0, 1)
        response = await ctx.http.get(API, params={"actor": asked})
        if response.status_code == 400:
            # "Profile not found", or not a valid handle: either way, no such account.
            await ctx.progress(1, 1)
            return
        if response.status_code >= 400:
            raise SourceUnavailable(
                "source_refused", host="public.api.bsky.app", status=response.status_code
            )
        profile: dict[str, Any] = response.json()
        handle = str(profile.get("handle") or asked)
        # The address WhatsMyName gives too, so that both findings make one trace.
        shown = asked if handle.casefold() == asked.casefold() else handle
        url = f"https://bsky.app/profile/{shown}"
        if target.kind != EntityKind.ACCOUNT:
            yield Finding(
                kind=EntityKind.ACCOUNT,
                value=url,
                relation="has_account",
                # A domain handle is proven; a username on bsky.social is only the same name.
                confidence=0.9 if target.kind == EntityKind.DOMAIN else 0.6,
                url=url,
                excerpt=(
                    f"Compte Bluesky « {handle} » ({profile.get('postsCount', 0)} publications)."
                ),
                attributes={
                    "site": "Bluesky",
                    **({"created": profile["createdAt"][:10]} if profile.get("createdAt") else {}),
                    **(
                        {"description": profile["description"]}
                        if profile.get("description")
                        else {}
                    ),
                },
            )
        domain_handle = not handle.endswith(f".{DEFAULT_DOMAIN}") and handle != INVALID_HANDLE
        if domain_handle and target.kind != EntityKind.DOMAIN:
            yield Finding(
                kind=EntityKind.DOMAIN,
                value=handle,
                relation="handle_domain",
                confidence=0.9,
                url=url,
                excerpt=(
                    f"Le compte Bluesky utilise le domaine « {handle} » comme pseudo : "
                    "Bluesky a vérifié que son titulaire contrôle ce domaine."
                ),
            )
        if profile.get("displayName"):
            yield Finding(
                kind=EntityKind.NAME,
                value=profile["displayName"],
                relation="shows_name",
                confidence=0.5,
                url=url,
                excerpt=f"Nom affiché sur le compte Bluesky « {handle} ».",
            )
        for finding in text_findings(
            profile.get("description") or "",
            url=url,
            where=f"dans la description du compte Bluesky « {handle} »",
            confidence=0.6,
        ):
            yield finding
        await ctx.progress(1, 1)
