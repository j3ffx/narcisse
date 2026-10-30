"""Gravatar: the public profile attached to an e-mail address, and the accounts it lists.

Gravatar finds a profile by the SHA-256 of the address, so the address itself is never sent. Its
API answers 100 requests an hour without a key; it resolves the primary address of a profile only.
"""

import hashlib
from collections.abc import AsyncIterator
from typing import Any, ClassVar

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
from narcisse.modules._text import read_on_profiles
from narcisse.notes import note

API = "https://api.gravatar.com/v3/profiles"


def email_hash(email: str) -> str:
    """Gravatar's identifier: the SHA-256 of the trimmed, lowercased address."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


class Gravatar(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="gravatar",
        title={
            "fr": "Gravatar",
            "en": "Gravatar",
        },
        description=(
            {
                "fr": (
                    "Le profil Gravatar associé à un email (nom affiché, lieu, comptes qu’il "
                    "liste). Seule l’empreinte SHA-256 de l’adresse est envoyée, jamais "
                    "l’adresse."
                ),
                "en": (
                    "The Gravatar profile tied to an email (display name, place, the accounts it "
                    "lists). Only the address's SHA-256 hash is sent, never the address."
                ),
            }
        ),
        category="accounts",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT, EntityKind.NAME}),
        hosts=("api.gravatar.com",),
        rate_limit=RateLimit(requests=1, per_seconds=2),
        max_parallel_runs=1,
        data_source="https://docs.gravatar.com/api/profiles/rest-api/",
    )

    def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        return read_on_profiles(self._run(ctx, target))

    async def _run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(0, 1)
        response = await ctx.http.get(f"{API}/{email_hash(target.normalized)}")
        if response.status_code == 404:
            await ctx.progress(1, 1)
            return
        if response.status_code >= 400:
            raise SourceUnavailable(
                "source_refused", host="api.gravatar.com", status=response.status_code
            )
        profile: dict[str, Any] = response.json()
        url = profile.get("profile_url") or f"https://gravatar.com/{profile.get('hash', '')}"
        yield Finding(
            kind=EntityKind.ACCOUNT,
            value=url,
            relation="has_account",
            confidence=0.9,  # found by the exact address
            url=url,
            note=note("gravatar_profile"),
            attributes={
                "site": "Gravatar",
                **{
                    k: profile[k]
                    for k in ("location", "job_title", "company", "description", "pronouns")
                    if profile.get(k)
                },
            },
        )
        if profile.get("display_name"):
            yield Finding(
                kind=EntityKind.NAME,
                value=profile["display_name"],
                relation="shows_name",
                confidence=0.7,
                url=url,
                note=note("gravatar_name"),
            )
        for account in profile.get("verified_accounts") or []:
            if account.get("is_hidden") or not account.get("url"):
                continue
            label = account.get("service_label") or account.get("service_type") or "?"
            yield Finding(
                kind=EntityKind.ACCOUNT,
                value=account["url"],
                relation="links_to",
                confidence=0.8,
                url=url,
                note=note("gravatar_account", site=label),
                attributes={"site": label},
            )
        await ctx.progress(1, 1)
