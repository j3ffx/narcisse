"""Keybase: an account found by its name, by an account it proved (GitHub, X, Reddit, Hacker News)
or by a domain it proved, and the identity proofs it publishes.

A Keybase proof is a signed statement posted on the other account or site: the two have the same
holder. Keybase has barely changed since Zoom bought it in 2020; its API still answers, but its
proofs may be old.
"""

import re
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

API = "https://keybase.io/_/api/1.0/user/lookup.json"
FIELDS = "basics,profile,proofs_summary,public_keys"
# The accounts Keybase can look a user up by, with how the UI names them.
PROVEN_SERVICES = {
    "github": "GitHub",
    "twitter": "X",
    "reddit": "Reddit",
    "hackernews": "Hacker News",
}
# Proofs of a site rather than of an account.
SITE_PROOFS = ("dns", "generic_web_site")
_USERNAME = re.compile(r"^[A-Za-z0-9_]{2,16}$")


def _account_name(url: str) -> str | None:
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    if parts.hostname != "keybase.io" or len(segments) != 1:
        return None
    return segments[0] if _USERNAME.match(segments[0]) else None


class Keybase(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="keybase",
        title="Keybase",
        description=(
            "Le compte Keybase d’un pseudo, ou celui qui a prouvé posséder le compte GitHub, X, "
            "Reddit ou Hacker News de ce pseudo, ou ce domaine ; et ses preuves d’identité, qui "
            "relient sûrement ses comptes et ses sites. Keybase n’évolue plus depuis 2020 : "
            "ses preuves peuvent être anciennes."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.USERNAME, EntityKind.DOMAIN, EntityKind.ACCOUNT}),
        produces=frozenset(
            {
                EntityKind.ACCOUNT,
                EntityKind.NAME,
                EntityKind.DOMAIN,
                EntityKind.URL,
                EntityKind.EMAIL,
            }
        ),
        hosts=("keybase.io",),
        rate_limit=RateLimit(requests=1, per_seconds=1),
        data_source="https://keybase.io/docs/api/1.0/call/user/lookup",
    )

    def accepts_target(self, kind: EntityKind, value: str) -> bool:
        if kind == EntityKind.ACCOUNT:
            return _account_name(value) is not None
        return super().accepts_target(kind, value)

    def _lookups(self, target: Target) -> list[tuple[str, str]]:
        """(field, value) pairs to look up, the account's own name first."""
        match target.kind:
            case EntityKind.DOMAIN:
                return [("domain", target.normalized)]
            case EntityKind.ACCOUNT:
                name = _account_name(target.value)
                return [("usernames", name)] if name else []
        own = [("usernames", target.value)] if _USERNAME.match(target.value) else []
        return own + [(service, target.value) for service in PROVEN_SERVICES]

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        lookups = self._lookups(target)
        seen: set[str] = set()
        for done, (field, value) in enumerate(lookups):
            await ctx.progress(done, len(lookups))
            response = await ctx.http.get(API, params={field: value, "fields": FIELDS})
            if response.status_code >= 400:
                raise SourceUnavailable(
                    "source_refused", host="keybase.io", status=response.status_code
                )
            body: dict[str, Any] = response.json()
            if (body.get("status") or {}).get("code") != 0:
                continue  # a value Keybase can't take (it says so instead of "not found")
            for user in body.get("them") or []:
                if not user or user.get("id") in seen:
                    continue
                seen.add(user["id"])
                for finding in self._user(target, field, value, user):
                    yield finding
        await ctx.progress(len(lookups), len(lookups))

    def _user(self, target: Target, field: str, value: str, user: dict[str, Any]) -> list[Finding]:
        username = user["basics"]["username"]
        # The address WhatsMyName gives too, so that both findings make one trace.
        shown = value if field == "usernames" and value.casefold() == username else username
        url = f"https://keybase.io/{shown}"
        profile = user.get("profile") or {}
        fingerprint = ((user.get("public_keys") or {}).get("primary") or {}).get("key_fingerprint")
        found: list[Finding] = []
        if target.kind != EntityKind.ACCOUNT:
            if field == "usernames":
                why, confidence = f"Compte Keybase « {username} ».", 0.6
            elif field == "domain":
                why = f"Le compte Keybase « {username} » a prouvé contrôler ce domaine."
                confidence = 0.9
            else:
                service = PROVEN_SERVICES[field]
                why = (
                    f"Le compte Keybase « {username} » a prouvé posséder le compte {service} "
                    f"« {value} »."
                )
                confidence = 0.5  # proven for that account, which may not be the user's
            found.append(
                Finding(
                    kind=EntityKind.ACCOUNT,
                    value=url,
                    relation="has_account",
                    confidence=confidence,
                    url=url,
                    excerpt=why,
                    attributes={
                        "site": "Keybase",
                        **({k: profile[k] for k in ("location", "bio") if profile.get(k)}),
                        **({"pgp": fingerprint.upper()} if fingerprint else {}),
                    },
                )
            )
        if profile.get("full_name"):
            found.append(
                Finding(
                    kind=EntityKind.NAME,
                    value=profile["full_name"],
                    relation="shows_name",
                    confidence=0.5,
                    url=url,
                    excerpt=f"Nom affiché sur le compte Keybase « {username} ».",
                )
            )
        found += text_findings(
            profile.get("bio") or "",
            url=url,
            where=f"dans la bio du compte Keybase « {username} »",
            confidence=0.5,
        )
        for proof in (user.get("proofs_summary") or {}).get("all") or []:
            found += self._proof(target, username, url, proof)
        return found

    def _proof(
        self, target: Target, username: str, url: str, proof: dict[str, Any]
    ) -> list[Finding]:
        kind_of = proof.get("proof_type", "")
        proven = proof.get("proof_url") or url
        if kind_of in SITE_PROOFS:
            domain = proof.get("nametag") or ""
            if not domain or (target.kind == EntityKind.DOMAIN and domain == target.normalized):
                return []
            return [
                Finding(
                    kind=EntityKind.DOMAIN,
                    value=domain,
                    relation="proves",
                    confidence=0.9,
                    url=proven,
                    excerpt=f"Domaine dont le compte Keybase « {username} » a prouvé le contrôle.",
                )
            ]
        if not proof.get("service_url"):
            return []
        service = PROVEN_SERVICES.get(kind_of, kind_of)
        return [
            Finding(
                kind=EntityKind.ACCOUNT,
                value=proof["service_url"],
                relation="proves",
                confidence=0.9,
                url=proven,
                excerpt=(
                    f"Compte {service} « {proof.get('nametag', '?')} » relié au compte Keybase "
                    f"« {username} » par une preuve d’identité signée."
                ),
                attributes={"site": service},
            )
        ]
