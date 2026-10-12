"""GitLab: a username's public profile on gitlab.com and on a few public instances, and the e-mail
addresses its recent commits carry.

Without an account, GitLab gives a user's name and public address, and their public activity; the
commits it points at carry their author's address, as on GitHub. gitlab.com shows the rest of a
profile (bio, place, site) only to a signed-in client: a free personal token, in the settings,
adds it.
"""

from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any, ClassVar
from urllib.parse import quote, urlsplit

import httpx

from narcisse.domain import EntityKind
from narcisse.engine.plugin import (
    Finding,
    ModuleContext,
    ModuleError,
    ModuleMeta,
    RateLimit,
    RateLimited,
    SourceModule,
    SourceUnavailable,
    Target,
)
from narcisse.modules._text import read_on_profiles, text_findings

MAIN = "gitlab.com"
INSTANCES = (MAIN, "framagit.org", "salsa.debian.org", "gitlab.gnome.org", "gitlab.freedesktop.org")
PUSHES_TO_READ = 50
COMMITS_TO_READ = 8


class _Missing(Exception):
    """Nothing there (404), or not shown to an anonymous client (403)."""


def _account_name(url: str) -> tuple[str, str] | None:
    """(instance, username) for a profile address on one of the instances."""
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    host = (parts.hostname or "").removeprefix("www.")
    if host not in INSTANCES or len(segments) != 1:
        return None
    return host, segments[0].removeprefix("@")


def _hidden(email: str, host: str) -> bool:
    """GitLab's addresses that hide the real one (`…@users.noreply.gitlab.com`)."""
    domain = email.rpartition("@")[2].lower()
    return domain.startswith("users.noreply.") or domain.endswith(f"noreply.{host}")


class GitLab(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="gitlab",
        title="GitLab",
        description=(
            "Le profil d’un pseudo sur gitlab.com, framagit.org, salsa.debian.org, GNOME et "
            "freedesktop.org (nom, email public) et les adresses email de ses commits récents. "
            "Sans compte ; un token personnel gratuit, dans les réglages, ajoute la bio, le lieu "
            "et le site des profils de gitlab.com."
        ),
        category="code",
        accepts=frozenset({EntityKind.USERNAME, EntityKind.ACCOUNT}),
        produces=frozenset({EntityKind.ACCOUNT, EntityKind.NAME, EntityKind.EMAIL, EntityKind.URL}),
        hosts=INSTANCES,
        rate_limit=RateLimit(requests=1, per_seconds=1),
        max_parallel_runs=1,
        data_source="https://docs.gitlab.com/api/users/",
    )

    def accepts_target(self, kind: EntityKind, value: str) -> bool:
        if kind == EntityKind.ACCOUNT:
            return _account_name(value) is not None
        return super().accepts_target(kind, value)

    def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        return read_on_profiles(self._run(ctx, target))

    async def _run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        if target.kind == EntityKind.ACCOUNT:
            found = _account_name(target.value)
            places = [found] if found else []
        else:
            places = [(host, target.value) for host in INSTANCES]
        notes: dict[str, int] = {"checked": 0, "found": 0, "unreachable": 0}
        for done, (host, username) in enumerate(places):
            await ctx.progress(done, len(places), notes)
            try:
                findings = [f async for f in self._instance(ctx, target, host, username)]
            except RateLimited:
                raise  # the run waits, then starts again (stored findings aren't told twice)
            except SourceUnavailable as exc:
                if exc.code == "gitlab_token_rejected":
                    raise
                notes["unreachable"] += 1
                continue
            except ModuleError:
                notes["unreachable"] += 1
                continue
            notes["checked"] += 1
            if findings:
                notes["found"] += 1
            for finding in findings:
                yield finding
        await ctx.progress(len(places), len(places), notes)

    async def _get(self, ctx: ModuleContext, host: str, path: str) -> Any:
        headers = {}
        if host == MAIN and ctx.preferences.gitlab_token:
            headers["PRIVATE-TOKEN"] = ctx.preferences.gitlab_token
        response: httpx.Response = await ctx.http.get(
            f"https://{host}/api/v4{path}", headers=headers
        )
        if response.status_code == 401 and headers:
            raise SourceUnavailable("gitlab_token_rejected")
        if response.status_code in (401, 403, 404):
            raise _Missing
        if response.status_code >= 400:
            raise SourceUnavailable("source_refused", host=host, status=response.status_code)
        return response.json()

    async def _instance(
        self, ctx: ModuleContext, target: Target, host: str, username: str
    ) -> AsyncIterator[Finding]:
        try:
            users = await self._get(ctx, host, f"/users?username={quote(username)}")
        except _Missing:
            return
        if not users:
            return
        user: dict[str, Any] = users[0]
        details: dict[str, Any] = {}
        if host != MAIN or ctx.preferences.gitlab_token:
            # Shown to anyone on some instances, to signed-in clients only on gitlab.com.
            with suppress(_Missing):
                details = await self._get(ctx, host, f"/users/{user['id']}")
        # The address WhatsMyName gives too, so that both findings make one trace.
        shown = username if user["username"].casefold() == username.casefold() else user["username"]
        url = f"https://{host}/{shown}"
        where = f"sur le profil GitLab « {user['username']} » ({host})"
        if target.kind != EntityKind.ACCOUNT:
            yield Finding(
                kind=EntityKind.ACCOUNT,
                value=url,
                relation="has_account",
                confidence=0.6,
                url=url,
                excerpt=f"Profil GitLab « {user['username']} » sur {host}.",
                attributes={
                    "site": "GitLab" if host == MAIN else f"GitLab ({host})",
                    **{
                        k: details[k]
                        for k in ("location", "organization", "job_title", "pronouns")
                        if details.get(k)
                    },
                },
            )
        if user.get("name"):
            yield Finding(
                kind=EntityKind.NAME,
                value=user["name"],
                relation="shows_name",
                confidence=0.5,
                url=url,
                excerpt=f"Nom affiché {where}.",
            )
        email = user.get("public_email") or details.get("public_email")
        if email:
            yield Finding(
                kind=EntityKind.EMAIL,
                value=email,
                relation="shows_email",
                confidence=0.7,
                url=url,
                excerpt=f"Email public {where}.",
            )
        for finding in self._details(details, url, where):
            yield finding
        async for finding in self._commits(ctx, host, user):
            yield finding

    def _details(self, details: dict[str, Any], url: str, where: str) -> list[Finding]:
        found: list[Finding] = []
        if details.get("website_url"):
            site = details["website_url"]
            site = site if "://" in site else f"https://{site}"
            found.append(
                Finding(
                    kind=EntityKind.URL,
                    value=site,
                    relation="links_to",
                    confidence=0.6,
                    url=url,
                    excerpt=f"Site indiqué {where}.",
                )
            )
        for key, address, label in (
            ("linkedin", "https://www.linkedin.com/in/{}", "LinkedIn"),
            ("twitter", "https://x.com/{}", "X"),
            ("github", "https://github.com/{}", "GitHub"),
        ):
            value = str(details.get(key) or "").strip().rstrip("/")
            if not value:
                continue
            account = value if "://" in value else address.format(value.removeprefix("@"))
            found.append(
                Finding(
                    kind=EntityKind.ACCOUNT,
                    value=account,
                    relation="links_to",
                    confidence=0.6,
                    url=url,
                    excerpt=f"Compte {label} indiqué {where}.",
                    attributes={"site": label},
                )
            )
        found += text_findings(details.get("bio") or "", url=url, where=where, confidence=0.6)
        return found

    async def _commits(
        self, ctx: ModuleContext, host: str, user: dict[str, Any]
    ) -> AsyncIterator[Finding]:
        """The addresses of the commits the user pushed lately, when they signed them under their
        own name (a push may carry someone else's commits)."""
        try:
            pushes = await self._get(
                ctx, host, f"/users/{user['id']}/events?action=pushed&per_page={PUSHES_TO_READ}"
            )
        except _Missing:
            return
        commits = dict.fromkeys(
            (event["project_id"], event["push_data"]["commit_to"])
            for event in pushes
            if event.get("project_id") and (event.get("push_data") or {}).get("commit_to")
        )
        names = {str(user.get("name") or "").casefold(), user["username"].casefold()} - {""}
        seen: set[str] = set()
        for project, sha in list(commits)[:COMMITS_TO_READ]:
            try:
                commit = await self._get(ctx, host, f"/projects/{project}/repository/commits/{sha}")
            except _Missing:
                continue
            email = str(commit.get("author_email") or "")
            if (
                "@" not in email
                or _hidden(email, host)
                or email.lower() in seen
                or str(commit.get("author_name") or "").casefold() not in names
            ):
                continue
            seen.add(email.lower())
            yield Finding(
                kind=EntityKind.EMAIL,
                value=email,
                relation="commits_as",
                confidence=0.7,
                url=commit.get("web_url"),
                excerpt=(
                    f"Adresse d’auteur d’un commit poussé par « {user['username']} » sur {host} "
                    f"(signé « {commit.get('author_name')} »)."
                ),
            )
