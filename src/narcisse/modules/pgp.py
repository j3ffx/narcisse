"""Public PGP keys: whether an e-mail address has a key on keys.openpgp.org, and which names and
addresses that key carries.

keys.openpgp.org only answers for addresses their owner verified, and allows one lookup by address
per minute (with a burst of 50). The machine-readable HKP index gives the fingerprint and the
identities without parsing the key itself.
"""

from collections.abc import AsyncIterator
from typing import ClassVar
from urllib.parse import quote, unquote

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
from narcisse.normalize import collapse

SERVER = "https://keys.openpgp.org"


def parse_index(text: str) -> tuple[str | None, list[str]]:
    """(fingerprint, identities) from a machine-readable HKP index (`pub:` and `uid:` lines)."""
    fingerprint = None
    identities = []
    for line in text.splitlines():
        fields = line.split(":")
        if fields[0] == "pub" and len(fields) > 1 and fingerprint is None:
            fingerprint = fields[1].upper() or None
        elif fields[0] == "uid" and len(fields) > 1 and fields[1]:
            identities.append(unquote(fields[1]))
    return fingerprint, identities


def split_identity(identity: str) -> tuple[str | None, str | None]:
    """« Jeanne Exemple (pro) <jeanne@example.org> » → (name, address)."""
    before, _, rest = identity.partition("<")
    address = rest.rstrip("> ").strip() or None
    name = collapse(before.split("(")[0]) or None
    return name, address


class PgpKeys(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="pgp",
        title="Clés PGP publiques",
        description=(
            "Cherche une clé PGP publiée pour un email sur keys.openpgp.org (seulement si son "
            "titulaire l’a vérifiée), avec les noms et adresses qu’elle porte."
        ),
        category="keys",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.URL, EntityKind.NAME, EntityKind.EMAIL}),
        hosts=("keys.openpgp.org",),
        rate_limit=RateLimit(requests=1, per_seconds=5),
        max_parallel_runs=1,
        data_source="https://keys.openpgp.org/about/api",
    )

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(0, 1)
        email = target.normalized
        response = await ctx.http.get(
            f"{SERVER}/pks/lookup?op=index&options=mr&search={quote(email)}"
        )
        if response.status_code == 404:
            await ctx.progress(1, 1)
            return
        if response.status_code >= 400:
            raise SourceUnavailable(
                "source_refused", host="keys.openpgp.org", status=response.status_code
            )
        fingerprint, identities = parse_index(response.text)
        page = f"{SERVER}/search?q={quote(email)}"
        yield Finding(
            kind=EntityKind.URL,
            value=page,
            relation="publishes_key",
            confidence=0.95,  # the owner verified this address
            url=page,
            excerpt=f"Une clé PGP publique est publiée pour {email}.",
            attributes={"fingerprint": fingerprint} if fingerprint else {},
        )
        for identity in identities:
            name, address = split_identity(identity)
            if name:
                yield Finding(
                    kind=EntityKind.NAME,
                    value=name,
                    relation="key_identity",
                    confidence=0.8,
                    url=page,
                    excerpt=f"Identité portée par la clé PGP : « {identity} ».",
                )
            if address and address.lower() != email:
                yield Finding(
                    kind=EntityKind.EMAIL,
                    value=address,
                    relation="key_identity",
                    confidence=0.8,
                    url=page,
                    excerpt=f"Autre adresse portée par la même clé PGP : « {identity} ».",
                )
        await ctx.progress(1, 1)
