"""What a domain's own site says about whoever runs it: the legal notice, the contact and "about"
pages often give a name, an address, a phone number, a SIREN.

Reads the home page and the few pages it links to that are about the publisher (legal notice,
contact, about, CV), on the domain itself only, as robots.txt allows. A redirection elsewhere is
a trace, not followed.
"""

import re
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin, urlsplit

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
from narcisse.modules._text import emails, is_profile, of

if TYPE_CHECKING:
    from narcisse.preferences import Preferences

MAX_PAGES = 5  # the home page and four about its publisher
MAX_REDIRECTS = 5
MAX_BYTES = 2_000_000
CONFIDENCE = 0.7  # the user's own site (a domain they declared), but a page may name others

_ABOUT = re.compile(
    r"mentions?[-_ ]?l[ée]gales?|legal|impressum|imprint|contact|about|a[-_ ]?propos|à propos|"
    r"qui[-_ ]suis[-_ ]je|qui[-_ ]sommes[-_ ]nous|\bcv\b|curriculum|resume",
    re.IGNORECASE,
)
_PHONE = re.compile(
    r"(?<![\d+])(?:\+33[\s.]?(?:\(0\))?[\s.]?[1-9]|0[1-9])(?:[\s.-]?\d{2}){4}(?!\d)"
    r"|(?<![\d+])\+(?:3[0-9]|4[0-9]|1)[\s.]?\d{1,4}(?:[\s.-]?\d{2,4}){2,4}(?!\d)"
)
_SIREN = re.compile(
    r"\b(?:SIREN|SIRET|RCS[^\d\n]{0,40}?|N°\s*TVA[^\d\n]{0,10}FR\s*\d{2})\s*:?\s*"
    r"(\d{3}[\s.]?\d{3}[\s.]?\d{3})(?:[\s.]?\d{5})?",
    re.IGNORECASE,
)
# A name: capitalized words (the keywords around it are matched in any case, the name isn't).
_NAME = r"([A-ZÀ-Ý][\w'’-]+(?:[ -](?:de |du |le |la )?[A-ZÀ-Ý][\w'’-]+){1,3})"
_PUBLISHER = re.compile(
    r"(?i:directeur|directrice|responsable)\s+(?i:de\s+)?(?i:la\s+)?(?i:publication)"
    r"(?:[^:\n]{0,60}?\s(?i:est)\s|\s*:\s*|\s+)(?:(?i:monsieur|madame|m\.|mme)\s+)?"
    + _NAME
    + r"|(?i:[ée]diteur(?:\s+du\s+site)?|propriétaire(?:\s+du\s+site)?)\s*:\s*"
    + _NAME
)
_ADDRESS = re.compile(
    r"\b\d{1,4}(?:\s?(?:bis|ter))?,?\s+(?:rue|avenue|av\.|boulevard|bd|chemin|place|allée|"
    r"impasse|route|quai|cours|square|lieu[- ]dit)\s[^\n,]{2,60},?\s+\d{5}\s+[A-ZÀ-Ý][\w' -]{1,40}",
    re.IGNORECASE,
)
# A number given as a registration (« n° 0784012789 »), not a phone.
_NUMBERED = re.compile(r"(?:n°|no\.?|numéro|siret|siren|rcs|tva)\s*:?\s*$", re.IGNORECASE)
# What a legal notice says of others: its host, the agency that made the site.
_THIRD_PARTY = re.compile(
    r"h[ée]berg|hosted|hosting|réalis|conception|conçu|développ|agence|prestataire",
    re.IGNORECASE,
)
THIRD_PARTY_CONFIDENCE = 0.3


def tidy_address(value: str) -> str:
    """One form for an address however its lines were split: « 7 rue X, 75000 Paris »."""
    match = re.match(r"(.*?)[\s,]+(\d{5})\s+(.*)", " ".join(value.split()))
    return f"{match.group(1)}, {match.group(2)} {match.group(3).strip()}" if match else value


@dataclass(frozen=True)
class Fetched:
    url: str  # where the page was read, after redirections within the site
    html: str | None = None
    elsewhere: str | None = None  # where it redirects, out of the site
    refused: bool = False  # robots.txt says no


class _Page(HTMLParser):
    """A page's visible text and its links (target, text)."""

    _HIDDEN = frozenset({"script", "style", "noscript", "template", "svg"})
    _BREAKS = frozenset({"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "address"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._hidden = 0
        self._link: list[str] | None = None
        self._href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._HIDDEN:
            self._hidden += 1
        elif tag in self._BREAKS:
            self.text.append("\n")
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._link = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self._HIDDEN and self._hidden:
            self._hidden -= 1
        elif tag == "a" and self._link is not None:
            self.links.append((self._href, " ".join("".join(self._link).split())))
            self._link = None

    def handle_data(self, data: str) -> None:
        if self._hidden:
            return
        self.text.append(" ".join(data.split("\n")))  # line breaks come from tags only
        if self._link is not None:
            self._link.append(data)

    @classmethod
    def read(cls, html: str) -> "_Page":
        page = cls()
        page.feed(html)
        page.close()
        return page

    @property
    def visible(self) -> str:
        lines = ("".join(self.text)).splitlines()
        return "\n".join(" ".join(line.split()) for line in lines if line.strip())


def siren_valid(digits: str) -> bool:
    """A SIREN's last digit is a Luhn check."""
    total = 0
    for i, char in enumerate(reversed(digits)):
        n = int(char) * (2 if i % 2 else 1)
        total += n - 9 if n > 9 else n
    return len(digits) == 9 and total % 10 == 0


def _around(text: str, start: int, end: int) -> str:
    snippet = " ".join(text[max(0, start - 50) : end + 50].split())
    return f"« …{snippet}… »"


@dataclass(frozen=True)
class Detail:
    kind: EntityKind
    value: str
    relation: str
    excerpt: str
    confidence: float = CONFIDENCE


def _detail(kind: EntityKind, value: str, relation: str, text: str, start: int, end: int) -> Detail:
    """A detail read at text[start:end]. Said of a host or an agency (in the same paragraph,
    before it), it is seldom the user's: low confidence."""
    paragraph = text[max(0, start - 320) : start].rsplit("\n", 1)[-1]
    third_party = bool(_THIRD_PARTY.search(paragraph))
    return Detail(
        kind,
        value,
        relation,
        _around(text, start, end),
        THIRD_PARTY_CONFIDENCE if third_party else CONFIDENCE,
    )


def details(text: str, html: str, links: list[tuple[str, str]]) -> Iterator[Detail]:
    """What a page gives about its publisher, or about others it names."""
    for email in emails(html, html=True):
        at = text.find(email)
        if at >= 0:
            yield _detail(EntityKind.EMAIL, email, "shows_email", text, at, at + len(email))
        else:
            yield Detail(EntityKind.EMAIL, email, "shows_email", "Lien mailto: de la page.")
    seen: set[str] = set()
    for match in _PHONE.finditer(text):
        key = re.sub(r"\D", "", match.group())[-9:]
        if key in seen or _NUMBERED.search(text[max(0, match.start() - 20) : match.start()]):
            continue
        seen.add(key)
        yield _detail(EntityKind.PHONE, match.group(), "shows_phone", text, *match.span())
    for href, _ in links:
        phone = href[4:].split("?")[0] if href.lower().startswith("tel:") else ""
        if phone and (key := re.sub(r"\D", "", phone)[-9:]) not in seen:
            seen.add(key)
            yield Detail(EntityKind.PHONE, phone, "shows_phone", "Lien tel: de la page.")
    for match in _SIREN.finditer(text):
        digits = re.sub(r"\D", "", match.group(1))
        if siren_valid(digits):
            yield _detail(EntityKind.ORGANIZATION, digits, "shows_siren", text, *match.span())
    for match in _PUBLISHER.finditer(text):
        name = (match.group(1) or match.group(2)).strip()
        yield _detail(EntityKind.NAME, name, "publisher", text, *match.span())
    for match in _ADDRESS.finditer(text):
        address = tidy_address(match.group())
        yield _detail(EntityKind.ADDRESS, address, "shows_address", text, *match.span())


class Website(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="website",
        title="Site du domaine",
        description=(
            "La page d’accueil du site d’un domaine et ses pages sur son éditeur (mentions "
            "légales, contact, à propos, CV) : nom, adresse, téléphone, email, SIREN, liens vers "
            "des profils. Seulement sur le domaine lui-même, comme robots.txt le permet."
        ),
        category="domains",
        accepts=frozenset({EntityKind.DOMAIN}),
        produces=frozenset(
            {
                EntityKind.URL,
                EntityKind.ACCOUNT,
                EntityKind.NAME,
                EntityKind.EMAIL,
                EntityKind.PHONE,
                EntityKind.ADDRESS,
                EntityKind.ORGANIZATION,
            }
        ),
        other_hosts="le site du domaine fouillé (et son www.)",
        rate_limit=RateLimit(requests=1, per_seconds=2),
        max_parallel_runs=2,
    )

    def allowed_hosts(
        self, preferences: "Preferences", target: Target | None = None
    ) -> tuple[str, ...]:
        if target is None or target.kind != EntityKind.DOMAIN:
            return ()
        return (target.normalized, f"www.{target.normalized}")

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        domain = target.normalized
        hosts = {domain, f"www.{domain}"}
        await ctx.progress(0, None)
        home = None
        for start in (f"https://{domain}/", f"https://www.{domain}/", f"http://{domain}/"):
            try:
                home = await self._fetch(ctx, start, hosts)
            except TransientError:
                continue
            break
        if home is None:
            raise SourceUnavailable("site_unreachable", host=domain)
        url, html, elsewhere = home.url, home.html, home.elsewhere
        if elsewhere is not None:
            yield Finding(
                kind=EntityKind.ACCOUNT if is_profile(elsewhere) else EntityKind.URL,
                value=elsewhere,
                relation="redirects_to",
                confidence=CONFIDENCE,
                url=url,
                excerpt=f"Le site {of(domain)} renvoie vers cette adresse.",
            )
            await ctx.progress(1, 1, {"pages": 0})
            return
        if html is None:
            await ctx.progress(1, 1, {"pages": 0, "robots": int(home.refused)})
            return

        page = _Page.read(html)
        about = []
        for href, text in page.links:
            link = urljoin(url, href).split("#")[0]
            parts = urlsplit(link)
            if (
                parts.scheme in ("http", "https")
                and parts.hostname in hosts
                and link.rstrip("/") != url.rstrip("/")
                and (_ABOUT.search(parts.path) or _ABOUT.search(text))
                and link not in about
            ):
                about.append(link)
        pages: list[tuple[str, str]] = [(url, html)]
        robots = 0
        for link in about[: MAX_PAGES - 1]:
            await ctx.progress(len(pages), len(about[: MAX_PAGES - 1]) + 1)
            try:
                fetched = await self._fetch(ctx, link, hosts)
            except (TransientError, SourceUnavailable):
                continue
            robots += fetched.refused
            if fetched.html is not None:
                pages.append((fetched.url, fetched.html))

        given: set[tuple[EntityKind, str]] = set()
        for index, (page_url, page_html) in enumerate(pages):
            read = page if index == 0 else _Page.read(page_html)
            found: dict[tuple[EntityKind, str], Detail] = {}
            for detail in details(read.visible, page_html, read.links):
                if (detail.kind, detail.value) not in given:
                    found.setdefault((detail.kind, detail.value), detail)
            accounts = [
                link
                for href, _ in read.links
                if (link := urljoin(page_url, href)).startswith("http") and is_profile(link)
            ]
            accounts = [a for a in dict.fromkeys(accounts) if (EntityKind.ACCOUNT, a) not in given]
            if not found and not accounts:
                continue
            via = None
            if index > 0:
                # The page itself, then what it says, related to it.
                yield Finding(
                    kind=EntityKind.URL,
                    value=page_url,
                    relation="has_page",
                    confidence=CONFIDENCE,
                    url=page_url,
                    excerpt=f"Page du site {of(domain)} sur son éditeur.",
                )
                via = (EntityKind.URL, page_url)
            for key, detail in found.items():
                given.add(key)
                yield Finding(
                    kind=detail.kind,
                    value=detail.value,
                    relation=detail.relation,
                    confidence=detail.confidence,
                    url=page_url,
                    excerpt=detail.excerpt,
                    content=page_html,
                    via=via,
                )
            for account in accounts:
                given.add((EntityKind.ACCOUNT, account))
                yield Finding(
                    kind=EntityKind.ACCOUNT,
                    value=account,
                    relation="links_to",
                    confidence=CONFIDENCE,
                    url=page_url,
                    excerpt=f"Lien vers un profil, sur le site {of(domain)}.",
                    via=via,
                )
        notes = {"pages": len(pages)}
        if robots:
            notes["robots"] = robots
        await ctx.progress(1, 1, notes)

    async def _fetch(self, ctx: ModuleContext, url: str, hosts: set[str]) -> Fetched:
        """A page of the site, following redirections within it only."""
        for _ in range(MAX_REDIRECTS):
            if not await ctx.http.allowed_by_robots(url):
                return Fetched(url, refused=True)
            response = await ctx.http.get(url, follow_redirects=False)
            if response.is_redirect and (location := response.headers.get("location")):
                target = urljoin(url, location)
                if urlsplit(target).hostname not in hosts:
                    return Fetched(url, elsewhere=target)
                url = target
                continue
            if response.status_code >= 400:
                raise SourceUnavailable(
                    "source_refused", host=urlsplit(url).hostname, status=response.status_code
                )
            if "html" not in response.headers.get("content-type", "html"):
                return Fetched(url)
            return Fetched(url, html=response.text[:MAX_BYTES])
        raise SourceUnavailable("source_refused", host=urlsplit(url).hostname)
