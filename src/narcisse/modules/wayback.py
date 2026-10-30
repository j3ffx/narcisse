"""What the Wayback Machine keeps of a domain's site or of a profile: pages archived even after
they were deleted (an old CV, a contact page, a profile closed since).

Asks the Internet Archive's CDX API (public, no account): which addresses were captured, and when.
It answers slowly and is sometimes offline; requests are spaced out, and a site its owner had
excluded from the archive says so.
"""

import json
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
from narcisse.notes import note

CDX = "https://web.archive.org/cdx/search/cdx"
WEB = "https://web.archive.org/web"
TIMEOUT = 60.0  # the CDX API takes its time on sites with many pages
MAX_URLS = 5000
MAX_NOTABLE = 25
# Pages about the person that ran a site: a CV, contact details, an "about" page, documents.
# A whole path segment naming a page about the person (not a word inside an article's title).
_NOTABLE_SEGMENT = re.compile(
    r"^(cv|curriculum(-vitae)?|resume|r[ée]sum[ée]|contact(ez-moi|-me|-us)?|about(-me|-us)?|"
    r"a-?propos|qui-suis-je|qui-sommes-nous|mentions?-?l[ée]gales?|impressum|imprint|legal|"
    r"moi|me|bio(graphie)?|portfolio)$",
    re.IGNORECASE,
)
_DOCUMENT = re.compile(r"\.(pdf|docx?|odt|rtf|xlsx?|pptx?|vcf)$", re.IGNORECASE)


def _day(timestamp: str) -> str:
    return f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}" if len(timestamp) >= 8 else ""


def _rows(text: str) -> list[dict[str, str]]:
    """The CDX JSON answer as dicts (its first row names the fields); [] if nothing is archived."""
    if not text.strip():
        return []
    data: Any = json.loads(text)
    if not isinstance(data, list) or len(data) < 2:
        return []
    header = data[0]
    return [dict(zip(header, row, strict=False)) for row in data[1:] if isinstance(row, list)]


def notable(original: str, mimetype: str) -> bool:
    """A page about whoever ran the site: a CV, a contact or "about" page, a document."""
    path = urlsplit(original).path
    segments = [segment.rsplit(".", 1)[0] for segment in path.split("/") if segment]
    return (
        any(_NOTABLE_SEGMENT.match(segment) for segment in segments)
        or bool(_DOCUMENT.search(path))
        or mimetype in ("application/pdf", "application/msword")
    )


class Wayback(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="wayback",
        title={
            "fr": "Archives du web (Wayback Machine)",
            "en": "Web archives (Wayback Machine)",
        },
        description=(
            {
                "fr": (
                    "Ce que la Wayback Machine d’Internet Archive garde d’un domaine ou d’un "
                    "profil : combien de pages, depuis quand, et celles qui parlent de toi (CV, "
                    "contact, à propos, documents), même supprimées depuis."
                ),
                "en": (
                    "What the Internet Archive's Wayback Machine keeps of a domain or a profile: "
                    "how many pages, since when, and the ones about you (CV, contact, about, "
                    "documents), even deleted since."
                ),
            }
        ),
        category="archives",
        accepts=frozenset({EntityKind.DOMAIN, EntityKind.ACCOUNT}),
        produces=frozenset({EntityKind.URL}),
        hosts=("web.archive.org",),
        rate_limit=RateLimit(requests=1, per_seconds=5),
        max_parallel_runs=1,
        data_source="https://archive.org/developers/wayback-cdx-server.html",
    )

    async def _cdx(self, ctx: ModuleContext, **params: str) -> list[dict[str, str]] | None:
        """The rows the CDX API gives, or None when the site is excluded from the archive."""
        response = await ctx.http.get(CDX, params={**params, "output": "json"}, timeout=TIMEOUT)
        if response.status_code == 403 and "blocked" in response.text.lower():
            return None
        if response.status_code >= 400:
            raise SourceUnavailable(
                "source_refused", host="web.archive.org", status=response.status_code
            )
        try:
            return _rows(response.text)
        except ValueError as exc:  # an HTML page: the archive is offline, or a challenge
            raise SourceUnavailable("source_unavailable", host="web.archive.org") from exc

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        if target.kind == EntityKind.DOMAIN:
            async for finding in self._domain(ctx, target.normalized):
                yield finding
        else:
            async for finding in self._page(ctx, target.normalized):
                yield finding

    async def _domain(self, ctx: ModuleContext, domain: str) -> AsyncIterator[Finding]:
        await ctx.progress(0, 2)
        rows = await self._cdx(
            ctx,
            url=domain,
            matchType="domain",
            fl="timestamp,original,mimetype,statuscode",
            collapse="urlkey",
            filter="statuscode:200",
            limit=str(MAX_URLS),
        )
        if rows is None:
            await ctx.progress(2, 2, {"archive_excluded": 1})
            return
        if not rows:
            await ctx.progress(2, 2, {"archived": 0})
            return
        await ctx.progress(1, 2)
        latest = await self._cdx(
            ctx, url=f"{domain}/", fl="timestamp", limit="-1", fastLatest="true"
        )
        first = min(row.get("timestamp", "") for row in rows)
        last = max([row.get("timestamp", "") for row in rows + (latest or [])])
        overview = f"{WEB}/*/{domain}*"
        yield Finding(
            kind=EntityKind.URL,
            value=overview,
            relation="archived_at",
            confidence=0.9,
            url=overview,
            note=note(
                "wayback_domain",
                count=len(rows),
                more=len(rows) >= MAX_URLS,
                domain=domain,
                first=_day(first),
                last=_day(last),
            ),
            attributes={
                "pages": len(rows),
                "first_capture": _day(first),
                "last_capture": _day(last),
            },
        )
        found = list(
            {
                urlsplit(row.get("original", "")).path.lower(): row
                for row in rows
                if notable(row.get("original", ""), row.get("mimetype", ""))
            }.values()
        )
        for row in found[:MAX_NOTABLE]:
            capture = f"{WEB}/{row['timestamp']}/{row['original']}"
            yield Finding(
                kind=EntityKind.URL,
                value=capture,
                relation="archived_page",
                confidence=0.8,
                url=capture,
                note=note("wayback_page", date=_day(row["timestamp"]), url=row["original"]),
                via=(EntityKind.URL, overview),
            )
        await ctx.progress(2, 2, {"archived": len(rows), "notable": len(found)})

    async def _page(self, ctx: ModuleContext, address: str) -> AsyncIterator[Finding]:
        await ctx.progress(0, 1)
        page = address.split("://", 1)[-1]
        rows = await self._cdx(ctx, url=page, fl="timestamp,statuscode", collapse="timestamp:6")
        if rows is None:
            await ctx.progress(1, 1, {"archive_excluded": 1})
            return
        kept = [row for row in rows if row.get("statuscode") in ("200", "-")] or rows
        if not kept:
            await ctx.progress(1, 1, {"archived": 0})
            return
        first, last = kept[0]["timestamp"], kept[-1]["timestamp"]
        capture = f"{WEB}/{last}/{address}"
        yield Finding(
            kind=EntityKind.URL,
            value=capture,
            relation="archived_at",
            confidence=0.9,
            url=capture,
            note=note("wayback_archived", months=len(kept), first=_day(first), last=_day(last)),
            attributes={"first_capture": _day(first), "last_capture": _day(last)},
        )
        await ctx.progress(1, 1, {"archived": len(kept)})
