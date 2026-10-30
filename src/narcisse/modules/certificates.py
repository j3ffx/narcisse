"""A domain's subdomains, as the public Certificate Transparency logs list them: every certificate
issued for a name is published there, so `nas.`, `vpn.` or `cloud.` of a personal domain show.

crt.sh first (every certificate ever logged; slow, and often down: 5 requests a minute, 502s);
Cert Spotter (SSLMate) when crt.sh can't answer, without an account (allowed for personal use;
certificates still valid only).
"""

from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
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
    TransientError,
)
from narcisse.notes import Note, note

CRT_SH = "https://crt.sh/"
CERT_SPOTTER = "https://api.certspotter.com/v1/issuances"
TIMEOUT = 60.0  # crt.sh takes its time on domains with many certificates
MAX_NAMES = 300
CERT_SPOTTER_PAGES = 5


@dataclass
class Seen:
    certificates: int = 0
    first: str = ""
    last: str = ""

    def add(self, not_before: str, not_after: str) -> None:
        self.certificates += 1
        if not_before and (not self.first or not_before < self.first):
            self.first = not_before
        if not_after and not_after > self.last:
            self.last = not_after


def names_in(
    entries: Iterable[tuple[Iterable[str], str, str]], domain: str
) -> tuple[dict[str, Seen], dict[str, Seen]]:
    """The subdomains and the e-mail addresses in certificates: (names, not before, not after)."""
    subdomains: dict[str, Seen] = {}
    emails: dict[str, Seen] = {}
    for names, not_before, not_after in entries:
        for raw in {n.strip().lower().removeprefix("*.") for n in names if n.strip()}:
            if "@" in raw:
                emails.setdefault(raw, Seen()).add(not_before[:10], not_after[:10])
            elif raw.endswith(f".{domain}"):
                subdomains.setdefault(raw, Seen()).add(not_before[:10], not_after[:10])
    return subdomains, emails


class Certificates(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="certificates",
        title={
            "fr": "Certificats (sous-domaines)",
            "en": "Certificates (subdomains)",
        },
        description=(
            {
                "fr": (
                    "Les sous-domaines d’un domaine que révèlent les journaux publics de "
                    "certificats (crt.sh, ou Cert Spotter quand crt.sh ne répond pas), et les "
                    "adresses email inscrites dans des certificats."
                ),
                "en": (
                    "The subdomains of a domain revealed by the public certificate logs (crt.sh, "
                    "or Cert Spotter when crt.sh doesn't answer), and the email addresses written"
                    " in certificates."
                ),
            }
        ),
        category="domains",
        accepts=frozenset({EntityKind.DOMAIN}),
        produces=frozenset({EntityKind.DOMAIN, EntityKind.EMAIL}),
        hosts=("crt.sh", "api.certspotter.com"),
        rate_limit=RateLimit(requests=1, per_seconds=15),  # crt.sh: 5 a minute per address
        max_parallel_runs=1,
        data_source="https://certificate.transparency.dev/",
    )

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        domain = target.normalized
        await ctx.progress(0, None)
        source = "crt.sh"
        try:
            entries = await self._crt_sh(ctx, domain)
        except (TransientError, SourceUnavailable):
            ctx.log.info("crt.sh can't answer for now: asking Cert Spotter")
            source = "Cert Spotter"
            entries = await self._cert_spotter(ctx, domain)
        subdomains, emails = names_in(entries, domain)
        latest = sorted(subdomains.items(), key=lambda item: item[1].last, reverse=True)
        for name, seen in latest[:MAX_NAMES]:
            yield Finding(
                kind=EntityKind.DOMAIN,
                value=name,
                relation="subdomain",
                confidence=0.9,
                url=f"{CRT_SH}?q={name}" if source == "crt.sh" else None,
                note=self._note("name", seen, source),
                attributes={"first_certificate": seen.first, "last_certificate": seen.last},
            )
        for email, seen in emails.items():
            yield Finding(
                kind=EntityKind.EMAIL,
                value=email,
                relation="certificate_email",
                confidence=0.6,
                url=f"{CRT_SH}?q={email}" if source == "crt.sh" else None,
                note=self._note("email", seen, source),
            )
        notes = {"certificates": len(entries), "subdomains": len(subdomains)}
        if len(subdomains) > MAX_NAMES:
            notes["truncated"] = len(subdomains) - MAX_NAMES
        await ctx.progress(1, 1, notes)

    @staticmethod
    def _note(what: str, seen: Seen, source: str) -> Note:
        return note(
            "certificates",
            what=what,
            count=seen.certificates,
            first=seen.first,
            last=seen.last,
            source=source,
        )

    async def _crt_sh(self, ctx: ModuleContext, domain: str) -> list[tuple[list[str], str, str]]:
        response = await ctx.http.get(
            CRT_SH, params={"q": f"%.{domain}", "output": "json"}, timeout=TIMEOUT
        )
        if response.status_code >= 400:
            raise SourceUnavailable("source_refused", host="crt.sh", status=response.status_code)
        try:
            rows: Any = response.json()
        except ValueError as exc:  # an HTML error page with a 200
            raise SourceUnavailable("source_unavailable", host="crt.sh") from exc
        if not isinstance(rows, list):
            raise SourceUnavailable("source_unavailable", host="crt.sh")
        return [
            (
                str(row.get("name_value") or "").splitlines(),
                str(row.get("not_before") or ""),
                str(row.get("not_after") or ""),
            )
            for row in rows
            if isinstance(row, dict)
        ]

    async def _cert_spotter(
        self, ctx: ModuleContext, domain: str
    ) -> list[tuple[list[str], str, str]]:
        entries: list[tuple[list[str], str, str]] = []
        after: str | None = None
        for _ in range(CERT_SPOTTER_PAGES):
            params = {"domain": domain, "include_subdomains": "true", "expand": "dns_names"}
            response = await ctx.http.get(
                CERT_SPOTTER, params={**params, **({"after": after} if after else {})}
            )
            if response.status_code >= 400:
                raise SourceUnavailable(
                    "source_refused", host="api.certspotter.com", status=response.status_code
                )
            page: Any = response.json()
            if not isinstance(page, list) or not page:
                break
            entries += [
                (
                    list(item.get("dns_names") or []),
                    str(item.get("not_before") or ""),
                    str(item.get("not_after") or ""),
                )
                for item in page
                if isinstance(item, dict)
            ]
            after = str(page[-1].get("id") or "") or None
            if after is None:
                break
        return entries
