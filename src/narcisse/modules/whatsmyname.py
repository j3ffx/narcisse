"""Accounts by username, on the ~700 sites of the WhatsMyName list.

One page per site, asked once, without logging in: the list says, for each site, which answer means
"this account exists" and which means "it doesn't". Narcisse never gets past an anti-bot defence:
sites marked as behind a captcha or a proof-of-work challenge are skipped, and a challenge page
counts as "couldn't tell". Its User-Agent stays honest, so sites that only answer browsers count
as "couldn't tell" too.

Data: WhatsMyName (https://github.com/WebBreacher/WhatsMyName), CC BY-SA 4.0, Micah Hoffman and
contributors; copy in `data/wmn-data.json`, refreshed by `scripts/update-wmn.py`.
"""

import asyncio
import json
from collections import Counter
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import quote, urlsplit

from narcisse.domain import EntityKind
from narcisse.engine.http import host_declared
from narcisse.engine.plugin import (
    Finding,
    ModuleContext,
    ModuleError,
    ModuleMeta,
    RateLimit,
    SourceModule,
    Target,
)

DATA = Path(__file__).parent / "data" / "wmn-data.json"
ADULT_CATEGORY = "xx NSFW xx"
# Getting past these would mean solving them: those sites are not asked at all.
SKIPPED_PROTECTIONS = frozenset({"captcha", "anubis"})
# Headers from the list that Narcisse sends; the others (browser User-Agents, cookies that accept
# a site's rules, anti-abuse headers) would make it pass for something it isn't.
NEUTRAL_HEADERS = frozenset({"accept", "accept-language", "content-type"})
PARALLEL_SITES = 16
SITE_TIMEOUT = 12.0
CHECKPOINT_EVERY = 25
CONFIDENCE = 0.5  # the name is taken there; whether by this person is for the user to say


class Verdict(StrEnum):
    FOUND = "found"
    MISSING = "missing"
    UNCERTAIN = "uncertain"  # an answer the list doesn't describe
    BLOCKED = "blocked"  # an anti-bot challenge
    UNREACHABLE = "unreachable"  # no answer, an error, a rate limit


@dataclass(frozen=True, kw_only=True)
class Site:
    name: str
    check_url: str
    pretty_url: str | None
    body: str | None
    headers: dict[str, str]
    exists_code: int
    exists_text: str
    missing_code: int
    missing_text: str
    category: str
    strip_chars: str
    protection: frozenset[str]

    @property
    def adult(self) -> bool:
        return self.category == ADULT_CATEGORY

    @property
    def skipped(self) -> bool:
        return bool(self.protection & SKIPPED_PROTECTIONS)

    def url(self, template: str, username: str) -> str:
        account = username.translate({ord(c): None for c in self.strip_chars})
        return template.replace("{account}", quote(account, safe="@.-_~"))


def load_sites(path: Path = DATA) -> list[Site]:
    raw = json.loads(path.read_text(encoding="utf-8"))["sites"]
    sites = []
    for s in raw:
        if s.get("valid") is False:
            continue
        sites.append(
            Site(
                name=s["name"],
                check_url=s["uri_check"],
                pretty_url=s.get("uri_pretty"),
                body=s.get("post_body"),
                headers={
                    k: str(v)
                    for k, v in (s.get("headers") or {}).items()
                    if k.lower() in NEUTRAL_HEADERS
                },
                exists_code=int(s["e_code"]),
                exists_text=s["e_string"],
                missing_code=int(s["m_code"]),
                missing_text=s["m_string"],
                category=s["cat"],
                strip_chars=s.get("strip_bad_char", ""),
                protection=frozenset(s.get("protection", [])),
            )
        )
    return sites


def host_pattern(url: str) -> str:
    """The host a URL template reaches; a username in the host becomes `*`."""
    host = urlsplit(url.replace("{account}", "x0x")).hostname or ""
    return ".".join("*" if "x0x" in label else label for label in host.split("."))


def is_challenge(status: int, headers: Any, body: str) -> bool:
    """An anti-bot page (Cloudflare, DDoS-Guard…) rather than the site's own answer."""
    if headers.get("cf-mitigated") == "challenge":
        return True
    return status in (403, 429, 503) and any(
        mark in body for mark in ("challenge-platform", "Just a moment...", "ddos-guard")
    )


def judge(site: Site, status: int, headers: Any, body: str) -> Verdict:
    if is_challenge(status, headers, body):
        return Verdict.BLOCKED
    if status == site.exists_code and site.exists_text in body:
        return Verdict.FOUND
    if status == site.missing_code and (not site.missing_text or site.missing_text in body):
        return Verdict.MISSING
    return Verdict.UNCERTAIN


SITES = load_sites()


class WhatsMyName(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="whatsmyname",
        title="Comptes par pseudo",
        description=(
            "Cherche le pseudo sur plus de 600 sites (réseaux sociaux, jeux, code, forums…) avec "
            "la liste publique WhatsMyName : une seule page demandée par site, sans connexion. "
            "Les sites protégés par un captcha sont ignorés."
        ),
        category="accounts",
        accepts=frozenset({EntityKind.USERNAME}),
        produces=frozenset({EntityKind.ACCOUNT}),
        hosts=tuple(sorted({host_pattern(s.check_url) for s in SITES})),
        rate_limit=RateLimit(requests=1, per_seconds=2),
        max_parallel_runs=2,
        licence="Liste WhatsMyName : CC BY-SA 4.0, Micah Hoffman et contributeurs",
        data_source="https://github.com/WebBreacher/WhatsMyName",
    )

    def __init__(self, sites: list[Site] | None = None) -> None:
        self.sites = SITES if sites is None else sites

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        username = target.value
        state = dict(ctx.checkpoint or {})
        done: set[str] = set(state.get("done", []))
        notes: Counter[str] = Counter(state.get("notes", {}))
        exclude_adult = ctx.preferences.exclude_adult
        to_check = []
        for site in self.sites:
            if site.name in done:
                continue
            if site.skipped:
                notes["skipped"] += 1
                done.add(site.name)
            elif site.adult and exclude_adult:
                notes["excluded"] += 1
                done.add(site.name)
            else:
                to_check.append(site)
        total = len(self.sites)
        limit = asyncio.Semaphore(PARALLEL_SITES)

        async def check(site: Site) -> tuple[Site, Verdict]:
            async with limit:
                await ctx.pause_point()
                return site, await self._check(ctx, site, username)

        tasks = [asyncio.create_task(check(site)) for site in to_check]
        try:
            for finished, next_one in enumerate(asyncio.as_completed(tasks), start=1):
                site, verdict = await next_one
                done.add(site.name)
                notes["checked" if verdict != Verdict.UNREACHABLE else "unreachable"] += 1
                if verdict in (Verdict.BLOCKED, Verdict.UNCERTAIN):
                    notes[verdict.value] += 1
                if verdict == Verdict.FOUND:
                    notes["found"] += 1
                    yield self._finding(site, username)
                await ctx.progress(len(done), total, dict(notes))
                if finished % CHECKPOINT_EVERY == 0:
                    await ctx.save_checkpoint({"done": sorted(done), "notes": dict(notes)})
        finally:
            for task in tasks:
                task.cancel()
        await ctx.progress(total, total, dict(notes))

    async def _check(self, ctx: ModuleContext, site: Site, username: str) -> Verdict:
        url = site.url(site.check_url, username)
        if not host_declared(urlsplit(url).hostname or "", self.meta.hosts):
            # A username with a dot, put in a host name, makes another subdomain level.
            return Verdict.UNCERTAIN
        verdict, redirected = await self._ask(ctx, site, url, username, follow_redirects=False)
        if verdict == Verdict.UNCERTAIN and redirected:
            # Some sites moved (http → https, a new path) since the list was written: when it
            # expects a page and got a redirect, the page at the end of it is what it describes.
            verdict, _ = await self._ask(ctx, site, url, username, follow_redirects=True)
        return verdict

    async def _ask(
        self, ctx: ModuleContext, site: Site, url: str, username: str, *, follow_redirects: bool
    ) -> tuple[Verdict, bool]:
        """The verdict, and whether the answer was a redirect the list doesn't expect."""
        try:
            response = await ctx.http.request(
                "POST" if site.body else "GET",
                url,
                content=site.url(site.body, username) if site.body else None,
                headers=site.headers,
                # The list's codes are those of the first answer (a redirect may mean "missing").
                follow_redirects=follow_redirects,
                timeout=SITE_TIMEOUT,
            )
        except ModuleError:
            return Verdict.UNREACHABLE, False
        unexpected = response.is_redirect and not 300 <= site.exists_code < 400
        return judge(site, response.status_code, response.headers, response.text), unexpected

    def _finding(self, site: Site, username: str) -> Finding:
        url = site.url(site.pretty_url or site.check_url, username)
        suffix = " (site adulte)" if site.adult else ""
        return Finding(
            kind=EntityKind.ACCOUNT,
            value=url,
            relation="has_account",
            confidence=CONFIDENCE,
            url=url,
            excerpt=f"Un compte « {username} » existe sur {site.name}{suffix}.",
            attributes={"site": site.name, "category": site.category, "adult": site.adult},
        )
