"""GitHub: a username's public profile and the e-mail addresses its commits carry; for an e-mail,
the accounts whose commits carry it.

Commit e-mails are a classic leak: Git records the author's address in every commit, and a public
repository publishes it. GitHub's REST API answers 60 requests an hour without an account; a free
personal token (in the settings) raises that to 5,000.
"""

import time
from collections.abc import AsyncIterator
from typing import Any, ClassVar
from urllib.parse import quote

import httpx

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
from narcisse.notes import note

API = "https://api.github.com"
REPOS_TO_READ = 5  # the most recently pushed ones
COMMITS_PER_REPO = 50
# Addresses GitHub gives to hide the real one: nothing leaks through them.
HIDDEN_EMAIL_DOMAIN = "users.noreply.github.com"


def _headers(ctx: ModuleContext) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if ctx.preferences.github_token:
        headers["Authorization"] = f"Bearer {ctx.preferences.github_token}"
    return headers


async def _get(ctx: ModuleContext, path: str) -> httpx.Response | None:
    """A GET on the API; None when there is nothing there (404, or 422 for unknown users)."""
    response = await ctx.http.get(f"{API}{path}", headers=_headers(ctx))
    if response.status_code in (404, 422):
        return None
    if response.status_code in (403, 429) and response.headers.get("x-ratelimit-remaining") == "0":
        reset = float(response.headers.get("x-ratelimit-reset", time.time() + 60))
        raise RateLimited(max(1.0, reset - time.time()), host="api.github.com")
    if response.status_code == 401:
        raise SourceUnavailable("github_token_rejected")
    if response.status_code >= 400:
        raise SourceUnavailable(
            "source_refused", host="api.github.com", status=response.status_code
        )
    return response


def _commit_email(email: str | None) -> str | None:
    if not email or "@" not in email or email.endswith(HIDDEN_EMAIL_DOMAIN):
        return None
    return email


class GitHub(SourceModule):
    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="github",
        title={
            "fr": "GitHub",
            "en": "GitHub",
        },
        description=(
            {
                "fr": (
                    "Le profil public d’un pseudo GitHub et les adresses email visibles dans ses "
                    "commits ; pour un email, les comptes dont les commits le portent. Sans "
                    "compte ; un token personnel gratuit, dans les réglages, relève la limite de "
                    "60 à 5 000 requêtes par heure."
                ),
                "en": (
                    "The public profile of a GitHub username and the email addresses visible in "
                    "its commits; for an email, the accounts whose commits bear it. No account "
                    "needed; a free personal token, in the settings, raises the limit from 60 to "
                    "5,000 requests an hour."
                ),
            }
        ),
        category="code",
        accepts=frozenset({EntityKind.USERNAME, EntityKind.EMAIL}),
        produces=frozenset({EntityKind.ACCOUNT, EntityKind.NAME, EntityKind.EMAIL, EntityKind.URL}),
        hosts=("api.github.com",),
        rate_limit=RateLimit(requests=1, per_seconds=1),
        max_parallel_runs=1,
        data_source="https://docs.github.com/rest",
    )

    def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        return read_on_profiles(self._run(ctx, target))

    async def _run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        if target.kind == EntityKind.EMAIL:
            async for finding in self._by_email(ctx, target.normalized):
                yield finding
        else:
            async for finding in self._by_username(ctx, target.value):
                yield finding

    async def _by_username(self, ctx: ModuleContext, username: str) -> AsyncIterator[Finding]:
        await ctx.progress(0, 2 + REPOS_TO_READ)
        response = await _get(ctx, f"/users/{quote(username)}")
        if response is None:
            await ctx.progress(1, 1)
            return
        user: dict[str, Any] = response.json()
        login = user["login"]
        profile = user["html_url"]
        yield Finding(
            kind=EntityKind.ACCOUNT,
            value=profile,
            relation="has_account",
            confidence=0.6,
            url=profile,
            note=note("github_profile", login=login, repos=user.get("public_repos", 0)),
            attributes={
                "site": "GitHub",
                **{k: user[k] for k in ("location", "company", "bio") if user.get(k)},
            },
        )
        if user.get("name"):
            yield Finding(
                kind=EntityKind.NAME,
                value=user["name"],
                relation="shows_name",
                confidence=0.5,
                url=profile,
                note=note("github_name", login=login),
            )
        if _commit_email(user.get("email")):
            yield Finding(
                kind=EntityKind.EMAIL,
                value=user["email"],
                relation="shows_email",
                confidence=0.7,
                url=profile,
                note=note("github_email", login=login),
            )
        if user.get("blog"):
            blog = user["blog"] if "://" in user["blog"] else f"https://{user['blog']}"
            yield Finding(
                kind=EntityKind.URL,
                value=blog,
                relation="links_to",
                confidence=0.6,
                url=profile,
                note=note("github_site", login=login),
            )
        if user.get("twitter_username"):
            yield Finding(
                kind=EntityKind.ACCOUNT,
                value=f"https://x.com/{user['twitter_username']}",
                relation="links_to",
                confidence=0.6,
                url=profile,
                note=note("github_x", login=login),
            )
        for finding in text_findings(
            user.get("bio") or "",
            url=profile,
            where=note("in_github_bio", login=login),
            confidence=0.6,
        ):
            yield finding
        await ctx.progress(1, 2 + REPOS_TO_READ)

        repos = await _get(ctx, f"/users/{quote(login)}/repos?type=owner&sort=pushed&per_page=20")
        own = [r for r in (repos.json() if repos else []) if not r.get("fork")][:REPOS_TO_READ]
        seen: set[str] = set()
        for i, repo in enumerate(own, start=2):
            await ctx.progress(i, 2 + len(own))
            commits = await _get(
                ctx,
                f"/repos/{repo['full_name']}/commits?author={quote(login)}"
                f"&per_page={COMMITS_PER_REPO}",
            )
            for commit in commits.json() if commits else []:
                author = commit.get("commit", {}).get("author") or {}
                email = _commit_email(author.get("email"))
                if email is None or email.lower() in seen:
                    continue
                seen.add(email.lower())
                yield Finding(
                    kind=EntityKind.EMAIL,
                    value=email,
                    relation="commits_as",
                    confidence=0.7,
                    url=commit.get("html_url"),
                    note=note(
                        "github_commit_email",
                        login=login,
                        repo=repo["full_name"],
                        author=author.get("name", "?"),
                    ),
                )
        await ctx.progress(1, 1)

    async def _by_email(self, ctx: ModuleContext, email: str) -> AsyncIterator[Finding]:
        await ctx.progress(0, 1)
        response = await _get(ctx, f"/search/commits?q=author-email:{quote(email)}&per_page=50")
        logins: dict[str, dict[str, Any]] = {}
        for item in response.json().get("items", []) if response else []:
            login = (item.get("author") or {}).get("login")
            if login and login not in logins:
                logins[login] = item
        for login, item in logins.items():
            yield Finding(
                kind=EntityKind.ACCOUNT,
                value=f"https://github.com/{login}",
                relation="commits_as",
                confidence=0.8,
                url=item.get("html_url"),
                note=note(
                    "github_commits_by",
                    login=login,
                    repo=item.get("repository", {}).get("full_name", "?"),
                ),
                attributes={"site": "GitHub"},
            )
        await ctx.progress(1, 1)
