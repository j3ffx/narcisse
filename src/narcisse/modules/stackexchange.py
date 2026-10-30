"""Stack Exchange: the Stack Overflow users who show a given name, and their accounts across the
network.

Display names aren't unique there: only the users whose name is exactly the one given are kept,
and they stay "to check"; the network's other accounts are looked up when only one user has that
name. The API answers 300 requests a day per address without a key; a run uses one or two.
"""

import time
from collections.abc import AsyncIterator
from html import unescape
from typing import Any, ClassVar

from narcisse.domain import EntityKind
from narcisse.engine.plugin import (
    Finding,
    ModuleContext,
    ModuleMeta,
    RateLimit,
    RateLimited,
    SourceModule,
    SourceUnavailable,
    Target,
)
from narcisse.modules._text import read_on_profiles, text_findings
from narcisse.normalize import fold
from narcisse.notes import note

API = "https://api.stackexchange.com/2.3"
# The default fields of a user, plus `about_me` (made once with /filters/create; filters don't
# expire).
USER_FILTER = "!SyjNqbwGU2NWZ1y5pj"
MAX_USERS = 5
CONFIDENCE = 0.3  # the same display name, nothing more
DAY = 86_400


def _seconds_to_midnight_utc() -> float:
    return DAY - time.time() % DAY


class StackExchange(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="stackexchange",
        title={
            "fr": "Stack Exchange",
            "en": "Stack Exchange",
        },
        description=(
            {
                "fr": (
                    "Les utilisateurs de Stack Overflow qui affichent exactement ce nom ou ce "
                    "pseudo (lieu, site, présentation) et, s’il n’y en a qu’un, ses comptes sur "
                    "les autres sites du réseau Stack Exchange. Les noms affichés ne sont pas "
                    "uniques : des homonymes sont possibles. 300 requêtes par jour sans compte, "
                    "une ou deux par recherche."
                ),
                "en": (
                    "The Stack Overflow users showing exactly this name or username (place, "
                    "website, about) and, if there is only one, their accounts on the other Stack"
                    " Exchange sites. Display names aren't unique: namesakes are possible. 300 "
                    "requests a day without an account, one or two per search."
                ),
            }
        ),
        category="forums",
        accepts=frozenset({EntityKind.USERNAME, EntityKind.NAME}),
        produces=frozenset({EntityKind.ACCOUNT, EntityKind.URL, EntityKind.EMAIL}),
        hosts=("api.stackexchange.com",),
        rate_limit=RateLimit(requests=1, per_seconds=2),
        max_parallel_runs=1,
        data_source="https://api.stackexchange.com/docs",
    )

    async def _get(self, ctx: ModuleContext, path: str, params: dict[str, Any]) -> list[Any]:
        response = await ctx.http.get(f"{API}{path}", params=params)
        body: dict[str, Any] = response.json() if response.content else {}
        if body.get("error_name") == "throttle_violation" or body.get("quota_remaining") == 0:
            # Out of requests for the day (the quota starts again at midnight UTC).
            raise RateLimited(_seconds_to_midnight_utc(), host="api.stackexchange.com")
        if response.status_code >= 400:
            raise SourceUnavailable(
                "source_refused", host="api.stackexchange.com", status=response.status_code
            )
        if body.get("backoff"):
            # The API asks to wait that long before the next request.
            await ctx.sleep(float(body["backoff"]))
        return list(body.get("items") or [])

    def _same_name(self, target: Target, shown: str) -> bool:
        if target.kind == EntityKind.NAME:
            return fold(shown) == target.normalized
        return shown.casefold() == target.value.casefold()

    def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        return read_on_profiles(self._run(ctx, target))

    async def _run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(0, 2)
        users = await self._get(
            ctx,
            "/users",
            {
                "inname": target.value,
                "site": "stackoverflow",
                "order": "desc",
                "sort": "reputation",
                "pagesize": 100,
                "filter": USER_FILTER,
            },
        )
        same = [u for u in users if self._same_name(target, unescape(u.get("display_name", "")))]
        same = same[:MAX_USERS]
        await ctx.progress(1, 2)
        for user in same:
            for finding in self._user(user):
                yield finding
        # Several users with that name: their accounts elsewhere would only add homonyms.
        if len(same) == 1 and same[0].get("account_id"):
            for other in await self._get(
                ctx, f"/users/{same[0]['account_id']}/associated", {"pagesize": 100}
            ):
                if other.get("site_url") == "https://stackoverflow.com":
                    continue  # already told
                url = f"{other['site_url']}/users/{other['user_id']}"
                origin = f"https://stackoverflow.com/users/{same[0]['user_id']}"
                yield Finding(
                    kind=EntityKind.ACCOUNT,
                    value=url,
                    relation="has_account",
                    confidence=CONFIDENCE,
                    url=url,
                    note=note("stackexchange_same_holder", site=other.get("site_name", "?")),
                    attributes={"site": other.get("site_name", "Stack Exchange")},
                    via=(EntityKind.ACCOUNT, origin),
                )
        await ctx.progress(2, 2)

    def _user(self, user: dict[str, Any]) -> list[Finding]:
        name = unescape(user.get("display_name", ""))
        # Without the name in the address, as the network's other accounts are given.
        url = f"https://stackoverflow.com/users/{user['user_id']}"
        where = note("on_stackoverflow_profile", name=name)
        created = user.get("creation_date")
        found = [
            Finding(
                kind=EntityKind.ACCOUNT,
                value=url,
                relation="has_account",
                confidence=CONFIDENCE,
                url=url,
                note=note("stackoverflow_user", name=name, reputation=user.get("reputation", 0)),
                attributes={
                    "site": "Stack Overflow",
                    **({"location": unescape(user["location"])} if user.get("location") else {}),
                    **(
                        {"created": time.strftime("%Y-%m-%d", time.gmtime(created))}
                        if created
                        else {}
                    ),
                },
            )
        ]
        if user.get("website_url"):
            found.append(
                Finding(
                    kind=EntityKind.URL,
                    value=user["website_url"],
                    relation="links_to",
                    confidence=CONFIDENCE,
                    url=url,
                    note=note("site_given", where=where),
                )
            )
        found += text_findings(
            user.get("about_me") or "", html=True, url=url, where=where, confidence=CONFIDENCE
        )
        return found
