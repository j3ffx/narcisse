"""Hacker News: a username's account, its age, its karma and what its "about" says.

The official API (on Firebase) answers without an account and without a stated limit. Usernames
are case-sensitive there: the one given is asked as it is written.
"""

import re
import time
from collections.abc import AsyncIterator
from typing import Any, ClassVar
from urllib.parse import parse_qs, quote, urlsplit

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
from narcisse.modules._text import html_text, read_on_profiles, text_findings
from narcisse.notes import note

API = "https://hacker-news.firebaseio.com/v0/user"
# What Hacker News accepts in a username: anything else can't be one.
_USERNAME = re.compile(r"^[A-Za-z0-9_-]{2,15}$")


def _account_name(url: str) -> str | None:
    """The username in a `https://news.ycombinator.com/user?id=<name>` address."""
    parts = urlsplit(url)
    if parts.hostname != "news.ycombinator.com" or parts.path != "/user":
        return None
    names = parse_qs(parts.query).get("id")
    return names[0] if names else None


class HackerNews(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="hackernews",
        title={
            "fr": "Hacker News",
            "en": "Hacker News",
        },
        description=(
            {
                "fr": (
                    "Le compte Hacker News d’un pseudo : date de création, karma, et les liens et"
                    " adresses de sa présentation (« about »)."
                ),
                "en": (
                    "A username's Hacker News account: creation date, karma, and the links and "
                    "addresses of its “about”."
                ),
            }
        ),
        category="forums",
        accepts=frozenset({EntityKind.USERNAME, EntityKind.ACCOUNT}),
        produces=frozenset({EntityKind.ACCOUNT, EntityKind.URL, EntityKind.EMAIL}),
        hosts=("hacker-news.firebaseio.com",),
        rate_limit=RateLimit(requests=1, per_seconds=1),
        data_source="https://github.com/HackerNews/API",
    )

    def accepts_target(self, kind: EntityKind, value: str) -> bool:
        if kind == EntityKind.ACCOUNT:
            return _account_name(value) is not None
        return super().accepts_target(kind, value) and bool(_USERNAME.match(value))

    def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        return read_on_profiles(self._run(ctx, target))

    async def _run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        username = (
            _account_name(target.value) if target.kind == EntityKind.ACCOUNT else target.value
        )
        if not username or not _USERNAME.match(username):
            return
        await ctx.progress(0, 1)
        response = await ctx.http.get(f"{API}/{quote(username)}.json")
        if response.status_code >= 400:
            raise SourceUnavailable(
                "source_refused", host="hacker-news.firebaseio.com", status=response.status_code
            )
        user: dict[str, Any] | None = response.json()
        if not user:
            await ctx.progress(1, 1)
            return
        # The address WhatsMyName gives too, so that both findings make one trace.
        url = f"https://news.ycombinator.com/user?id={username}"
        about = user.get("about") or ""
        if target.kind != EntityKind.ACCOUNT:
            created = user.get("created")
            yield Finding(
                kind=EntityKind.ACCOUNT,
                value=url,
                relation="has_account",
                confidence=0.6,
                url=url,
                note=note("hackernews_account", username=username, karma=user.get("karma", 0)),
                attributes={
                    "site": "Hacker News",
                    **(
                        {"created": time.strftime("%Y-%m-%d", time.gmtime(created))}
                        if created
                        else {}
                    ),
                    **({"about": html_text(about)} if about else {}),
                },
            )
        for finding in text_findings(
            about,
            html=True,
            url=url,
            where=note("in_hackernews_about", username=username),
            confidence=0.6,
        ):
            yield finding
        await ctx.progress(1, 1)
