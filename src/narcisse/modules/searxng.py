"""Web pages that mention a name, a username, an address or a domain, through the user's own
SearXNG instance (a metasearch engine that runs on their machine: `narcisse searxng` sets one up).

Narcisse never asks a search engine itself; the instance does, as a browser would. Only results
that do contain what was searched are kept, as traces to check: a page that names you may be
about someone else.
"""

import re
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlsplit

from narcisse.domain import EntityKind
from narcisse.engine.plugin import (
    Finding,
    InputRejected,
    ModuleContext,
    ModuleMeta,
    RateLimit,
    SourceModule,
    SourceUnavailable,
    Target,
)
from narcisse.modules._text import is_profile
from narcisse.normalize import fold

if TYPE_CHECKING:
    from narcisse.preferences import Preferences

PAGES = 2  # about 20 results each
CONFIDENCE = 0.3  # a page that names you may be about a namesake


def query_for(target: Target) -> str:
    """The exact phrase; a domain is searched for outside of itself."""
    if target.kind == EntityKind.DOMAIN:
        return f'"{target.normalized}" -site:{target.normalized}'
    return f'"{target.value}"'


def mentions(target: Target, result: dict[str, Any]) -> bool:
    """Whether a result does contain what was searched (engines also return near matches)."""
    text = fold(" ".join(str(result.get(k) or "") for k in ("url", "title", "content")))
    if target.kind == EntityKind.PHONE:
        return target.normalized[-9:] in re.sub(r"[^0-9]", "", text)
    wanted = fold(target.value if target.kind == EntityKind.NAME else target.normalized)
    if target.kind == EntityKind.DOMAIN and urlsplit(str(result.get("url"))).hostname in (
        target.normalized,
        f"www.{target.normalized}",
    ):
        return False  # the domain's own pages: the site module reads them
    return wanted in text


class SearXNG(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="searxng",
        title="Recherche web (ton instance SearXNG)",
        description=(
            "Les pages web qui citent exactement un nom, un pseudo, un email ou un domaine, "
            "trouvées par ton instance SearXNG (un métamoteur qui tourne chez toi : "
            "« narcisse searxng » en installe une avec Docker). Narcisse n’interroge jamais un "
            "moteur de recherche lui-même."
        ),
        category="web",
        accepts=frozenset(
            {
                EntityKind.NAME,
                EntityKind.USERNAME,
                EntityKind.EMAIL,
                EntityKind.DOMAIN,
                EntityKind.PHONE,
            }
        ),
        produces=frozenset({EntityKind.URL, EntityKind.ACCOUNT}),
        other_hosts="ton instance SearXNG (son adresse, dans les réglages)",
        rate_limit=RateLimit(requests=1, per_seconds=3),
        max_parallel_runs=1,
        licence="SearXNG : AGPL-3.0 (lancé à part, pas embarqué)",
        data_source="https://docs.searxng.org/dev/search_api.html",
    )

    def unavailable(self, preferences: "Preferences") -> str | None:
        return None if preferences.searxng_url else "searxng_not_set"

    def allowed_hosts(
        self, preferences: "Preferences", target: Target | None = None
    ) -> tuple[str, ...]:
        host = urlsplit(preferences.searxng_url or "").hostname
        return (host,) if host else ()

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        base = ctx.preferences.searxng_url
        if not base:
            raise InputRejected("searxng_not_set")
        host = urlsplit(base).hostname
        query = query_for(target)
        seen: set[str] = set()
        kept = 0
        total = 0
        for page in range(1, PAGES + 1):
            await ctx.progress(page - 1, PAGES)
            response = await ctx.http.get(
                f"{base}/search", params={"q": query, "format": "json", "pageno": str(page)}
            )
            if response.status_code == 403:
                raise SourceUnavailable("searxng_json_off", host=host)
            if response.status_code >= 400:
                raise SourceUnavailable("source_refused", host=host, status=response.status_code)
            try:
                results = response.json().get("results") or []
            except (ValueError, AttributeError) as exc:
                raise SourceUnavailable("source_unavailable", host=host) from exc
            if not results:
                break
            for result in results:
                url = str(result.get("url") or "")
                total += 1
                if not url.startswith(("http://", "https://")) or url in seen:
                    continue
                seen.add(url)
                if not mentions(target, result):
                    continue
                kept += 1
                title = " ".join(str(result.get("title") or "").split())
                content = " ".join(str(result.get("content") or "").split())
                engines = result.get("engines") or [result.get("engine")]
                yield Finding(
                    kind=EntityKind.ACCOUNT if is_profile(url) else EntityKind.URL,
                    value=url,
                    relation="mentioned_on",
                    confidence=CONFIDENCE,
                    url=url,
                    excerpt=(f"{title} — {content}" if content else title)[:300] or None,
                    attributes={"engines": [e for e in engines if e]},
                )
        await ctx.progress(PAGES, PAGES, {"results": total, "found": kept})
