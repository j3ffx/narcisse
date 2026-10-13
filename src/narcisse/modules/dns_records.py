"""What a domain's DNS tells about whoever runs it: who receives its mail, who serves it, which
services it was verified with, and the addresses its records give out.

Asked of the machine's own resolver (the one every connection uses): no third party learns what
is looked up. The services are recognized from `data/dns-services.json`, kept by hand.
"""

import json
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, ClassVar

import dns.asyncresolver
import dns.exception
import dns.resolver
import dns.reversename

from narcisse.domain import EntityKind
from narcisse.engine.plugin import (
    Finding,
    InputRejected,
    ModuleContext,
    ModuleMeta,
    SourceModule,
    Target,
    TransientError,
)
from narcisse.modules._text import of

DATA: dict[str, Any] = json.loads(
    (Path(__file__).parent / "data" / "dns-services.json").read_text("utf-8")
)
FREE_MAIL = frozenset(DATA["free_mail"])
TIMEOUT = 8.0
_MAILTO = re.compile(r"mailto:([^,;!\s]+)", re.IGNORECASE)


class DomainMissing(Exception):
    """The name doesn't exist in the DNS (NXDOMAIN)."""


def service_of(table: str, host: str) -> str | None:
    """The service a host belongs to: a key ending in "-" or "." is a part of the name
    (`awsdns-`), any other a suffix (`google.com` for `aspmx.l.google.com`)."""
    host = host.lower().rstrip(".")
    for key, service in DATA[table].items():
        if key.endswith(("-", ".")):
            if key in host:
                return str(service)
        elif host == key or host.endswith(f".{key}"):
            return str(service)
    return None


def verified_with(record: str) -> str | None:
    lowered = record.lower()
    for prefix, service in DATA["txt"].items():
        if lowered.startswith(prefix.lower()):
            return str(service)
    return None


def spf_includes(record: str) -> list[str]:
    """The domains an SPF record lets send mail (its `include:` and `redirect=`)."""
    found: list[str] = []
    for part in record.split():
        term = part.lower().lstrip("+-~?")
        if term.startswith("include:"):
            found.append(term.removeprefix("include:"))
        elif term.startswith("redirect="):
            found.append(term.removeprefix("redirect="))
    return found


def soa_email(rname: str) -> str | None:
    """The address in an SOA record: `hostmaster.example.org.` is hostmaster@example.org (a dot
    escaped with a backslash belongs to the local part)."""
    match = re.match(r"^((?:[^.\\]|\\.)+)\.(.+)$", rname.rstrip("."))
    if not match:
        return None
    return f"{match.group(1).replace('\\.', '.')}@{match.group(2)}"


def personal_enough(email: str, domain: str) -> bool:
    """Whether an address in a record may be the user's: one of their domain, or of a webmail.
    Addresses of a host or a DMARC service are theirs, not the user's."""
    host = email.rsplit("@", 1)[-1].lower()
    return host == domain or host.endswith(f".{domain}") or host in FREE_MAIL


class Dns(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="dns",
        title="DNS du domaine",
        description=(
            "Ce que les enregistrements DNS d’un domaine révèlent : qui reçoit ses emails, qui "
            "l’héberge, les services auprès desquels il a été vérifié (Google, Microsoft, "
            "Facebook…), et les adresses email qu’ils citent."
        ),
        category="domains",
        accepts=frozenset({EntityKind.DOMAIN}),
        produces=frozenset({EntityKind.ORGANIZATION, EntityKind.EMAIL}),
        other_hosts="le résolveur DNS de ta machine, comme pour toute connexion",
        max_parallel_runs=2,
        data_source="https://www.dnspython.org/",
        licence="dnspython : ISC",
    )

    async def query(self, name: str, rdtype: str) -> list[str]:
        """The records of a type, as text (TXT strings joined, MX hosts, SOA's rname); [] when
        there are none. Raises `DomainMissing` when the name doesn't exist."""
        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = TIMEOUT
        try:
            answer = await resolver.resolve(name, rdtype)
        except dns.resolver.NXDOMAIN as exc:
            raise DomainMissing(name) from exc
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            return []
        except dns.exception.Timeout as exc:
            raise TransientError("source_timeout", host="DNS") from exc
        texts: list[str] = []
        for record in answer:
            if rdtype == "TXT":
                texts.append(b"".join(record.strings).decode("utf-8", "replace"))
            elif rdtype == "MX":
                texts.append(str(record.exchange))
            elif rdtype == "SOA":
                texts.append(str(record.rname))
            else:
                texts.append(record.to_text())
        return texts

    async def _records(self, name: str, rdtype: str) -> list[str]:
        try:
            return await self.query(name, rdtype)
        except DomainMissing:
            return []

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        domain = target.normalized
        await ctx.progress(0, 7)
        try:
            mx = await self.query(domain, "MX")
        except DomainMissing as exc:
            raise InputRejected("domain_not_found", domain=domain) from exc
        services: dict[str, tuple[str, str]] = {}  # service → (what it does, the record)

        def seen(service: str | None, role: str, record: str) -> None:
            if service and service not in services:
                services[service] = (role, record)

        for host in mx:
            seen(service_of("mx", host), "mail", f"MX {host.rstrip('.')}")
        await ctx.progress(1, 7)
        for host in await self._records(domain, "NS"):
            seen(service_of("ns", host), "dns", f"NS {host.rstrip('.')}")
        await ctx.progress(2, 7)
        txt = await self._records(domain, "TXT")
        for record in txt:
            if record.lower().startswith("v=spf1"):
                for include in spf_includes(record):
                    seen(service_of("spf", include), "sending", f"SPF include:{include}")
            else:
                seen(verified_with(record), "verified", record[:60])
        for record in await self._records(f"_atproto.{domain}", "TXT"):
            seen(verified_with(record), "verified", f"_atproto {record[:60]}")
        await ctx.progress(3, 7)
        addresses = await self._records(domain, "A")
        for address in addresses:
            hosting = DATA["ip"].get(address)
            if hosting is None:
                ptr = await self._records(dns.reversename.from_address(address).to_text(), "PTR")
                hosting = next(filter(None, (service_of("ptr", p) for p in ptr)), None)
            seen(hosting, "hosting", f"A {address}")
        await ctx.progress(4, 7)

        for service, (role, record) in services.items():
            yield Finding(
                kind=EntityKind.ORGANIZATION,
                value=service,
                relation="uses_service",
                confidence=0.9,
                excerpt=EXCERPTS[role].format(
                    domain=domain, service=service, of_domain=of(domain), of_service=of(service)
                )
                + f" ({record}).",
                attributes={"service": role},
            )

        emails: dict[str, str] = {}
        for record in await self._records(f"_dmarc.{domain}", "TXT"):
            for address in _MAILTO.findall(record):
                emails.setdefault(address.lower(), "dmarc_reports")
        await ctx.progress(5, 7)
        for rname in await self._records(domain, "SOA"):
            if (contact := soa_email(rname)) is not None:
                emails.setdefault(contact.lower(), "dns_contact")
        await ctx.progress(6, 7)
        for address, relation in emails.items():
            if not personal_enough(address, domain):
                continue
            yield Finding(
                kind=EntityKind.EMAIL,
                value=address,
                relation=relation,
                confidence=0.5,
                excerpt=(
                    f"Adresse qui reçoit les rapports DMARC {of(domain)}."
                    if relation == "dmarc_reports"
                    else f"Adresse du responsable de la zone DNS {of(domain)} (SOA)."
                ),
            )
        await ctx.progress(
            7, 7, {"records": len(mx) + len(txt) + len(addresses), "services": len(services)}
        )


EXCERPTS = {
    "mail": "Les emails {of_domain} sont reçus par {service}",
    "dns": "Le DNS {of_domain} est servi par {service}",
    "sending": "{service} peut envoyer des emails au nom {of_domain}",
    "verified": "{domain} a été vérifié auprès {of_service}",
    "hosting": "Le site {of_domain} est hébergé chez {service}",
}
