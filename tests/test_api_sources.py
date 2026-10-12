"""The GitHub, Gravatar and PGP modules, against recorded-style answers (no network)."""

import time

import httpx
import pytest
import respx

from narcisse.domain import EntityKind
from narcisse.engine.plugin import RateLimited, SourceUnavailable
from narcisse.modules.github import GitHub
from narcisse.modules.gravatar import Gravatar, email_hash
from narcisse.modules.pgp import PgpKeys, parse_index, split_identity
from narcisse.preferences import Preferences
from tests.module_context import FakeContext, run, target

USER = {
    "login": "jeanne-exemple",
    "html_url": "https://github.com/jeanne-exemple",
    "name": "Jeanne Exemple",
    "email": None,
    "blog": "jeanne.example.org",
    "twitter_username": None,
    "location": "Lyon",
    "company": None,
    "bio": "Notes : https://notes.example.org",
    "public_repos": 2,
}


def commit(email: str, name: str = "Jeanne Exemple") -> dict[str, object]:
    return {
        "html_url": "https://github.com/jeanne-exemple/notes/commit/abc",
        "commit": {"author": {"email": email, "name": name}},
    }


# GitHub


@respx.mock
async def test_github_finds_the_profile_and_the_addresses_commits_carry(
    http_client: httpx.AsyncClient,
) -> None:
    respx.get("https://api.github.com/users/jeanne-exemple").respond(200, json=USER)
    respx.get(url__startswith="https://api.github.com/users/jeanne-exemple/repos").respond(
        200,
        json=[
            {"full_name": "jeanne-exemple/notes", "fork": False},
            {"full_name": "jeanne-exemple/fork", "fork": True},
        ],
    )
    respx.get(url__startswith="https://api.github.com/repos/jeanne-exemple/notes/commits").respond(
        200,
        json=[
            commit("jeanne@example.org"),
            commit("JEANNE@example.org"),  # the same address, told once
            commit("123+jeanne-exemple@users.noreply.github.com"),  # hidden: nothing leaks
        ],
    )
    module = GitHub()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.USERNAME, "jeanne-exemple")
    )

    assert [(f.kind, f.relation, f.value) for f in found] == [
        (EntityKind.ACCOUNT, "has_account", "https://github.com/jeanne-exemple"),
        (EntityKind.NAME, "shows_name", "Jeanne Exemple"),
        (EntityKind.URL, "links_to", "https://jeanne.example.org"),
        (EntityKind.URL, "links_to", "https://notes.example.org"),
        (EntityKind.EMAIL, "commits_as", "jeanne@example.org"),
    ]
    assert found[0].attributes["location"] == "Lyon"
    # Forks are someone else's commits.
    assert not any("fork/commits" in str(c.request.url) for c in respx.calls)


@respx.mock
async def test_github_finds_nothing_for_an_unknown_user(http_client: httpx.AsyncClient) -> None:
    respx.get("https://api.github.com/users/personne").respond(404)
    module = GitHub()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.USERNAME, "personne")
    )
    assert found == []


@respx.mock
async def test_github_finds_the_accounts_behind_an_address(
    http_client: httpx.AsyncClient,
) -> None:
    route = respx.get(url__startswith="https://api.github.com/search/commits").respond(
        200,
        json={
            "items": [
                {
                    "html_url": "https://github.com/a/b/commit/1",
                    "author": {"login": "jeanne-exemple"},
                    "repository": {"full_name": "a/b"},
                },
                {
                    "html_url": "https://github.com/a/b/commit/2",
                    "author": {"login": "jeanne-exemple"},
                },
                {"html_url": "https://github.com/a/b/commit/3", "author": None},
            ]
        },
    )
    module = GitHub()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.EMAIL, "jeanne@example.org")
    )
    assert [f.value for f in found] == ["https://github.com/jeanne-exemple"]
    assert "author-email:jeanne%40example.org" in str(route.calls.last.request.url)


@respx.mock
async def test_github_uses_the_optional_token(http_client: httpx.AsyncClient) -> None:
    route = respx.get("https://api.github.com/users/personne").respond(404)
    module = GitHub()
    ctx = FakeContext(module, http_client, preferences=Preferences(github_token="ghp_test"))
    await run(module, ctx, target(EntityKind.USERNAME, "personne"))
    assert route.calls.last.request.headers["Authorization"] == "Bearer ghp_test"


@respx.mock
async def test_github_out_of_requests_waits_until_the_reset(
    http_client: httpx.AsyncClient,
) -> None:
    respx.get("https://api.github.com/users/jeanne").respond(
        403,
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(time.time()) + 600)},
    )
    module = GitHub()
    with pytest.raises(RateLimited) as limited:
        await run(module, FakeContext(module, http_client), target(EntityKind.USERNAME, "jeanne"))
    assert 590 <= limited.value.retry_after <= 600


@respx.mock
async def test_github_says_when_the_token_is_refused(http_client: httpx.AsyncClient) -> None:
    respx.get("https://api.github.com/users/jeanne").respond(401)
    module = GitHub()
    ctx = FakeContext(module, http_client, preferences=Preferences(github_token="expired"))
    with pytest.raises(SourceUnavailable, match="github_token_rejected"):
        await run(module, ctx, target(EntityKind.USERNAME, "jeanne"))


# Gravatar


def test_gravatar_identifies_an_address_by_its_sha256() -> None:
    assert email_hash(" Jeanne@Example.org ") == email_hash("jeanne@example.org")
    assert len(email_hash("jeanne@example.org")) == 64


@respx.mock
async def test_gravatar_finds_the_profile_and_its_verified_accounts(
    http_client: httpx.AsyncClient,
) -> None:
    route = respx.get(
        f"https://api.gravatar.com/v3/profiles/{email_hash('jeanne@example.org')}"
    ).respond(
        200,
        json={
            "hash": email_hash("jeanne@example.org"),
            "profile_url": "https://gravatar.com/jeanneexemple",
            "display_name": "Jeanne E.",
            "location": "Lyon",
            "verified_accounts": [
                {"service_label": "Mastodon", "url": "https://social.example.org/@jeanne"},
                {"service_label": "Hidden", "url": "https://hidden.example.org", "is_hidden": True},
            ],
        },
    )
    module = Gravatar()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.EMAIL, "jeanne@example.org")
    )
    assert [(f.kind, f.value) for f in found] == [
        (EntityKind.ACCOUNT, "https://gravatar.com/jeanneexemple"),
        (EntityKind.NAME, "Jeanne E."),
        (EntityKind.ACCOUNT, "https://social.example.org/@jeanne"),
    ]
    # Only the hash travels, never the address.
    assert "jeanne" not in str(route.calls.last.request.url)


@respx.mock
async def test_gravatar_finds_nothing_without_a_profile(http_client: httpx.AsyncClient) -> None:
    respx.get(url__startswith="https://api.gravatar.com/v3/profiles/").respond(404)
    module = Gravatar()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.EMAIL, "jeanne@example.org")
    )
    assert found == []


# PGP

INDEX = (
    "info:1:1\n"
    "pub:0123456789abcdef0123456789abcdef01234567:1:4096:1700000000::\n"
    "uid:Jeanne%20Exemple%20%28pro%29%20%3Cjeanne%40example.org%3E:1700000000::\n"
    "uid:Jeanne%20Exemple%20%3Cjeanne%40example.net%3E:1700000000::\n"
)


def test_the_key_index_gives_the_fingerprint_and_the_identities() -> None:
    fingerprint, identities = parse_index(INDEX)
    assert fingerprint == "0123456789ABCDEF0123456789ABCDEF01234567"
    assert identities == [
        "Jeanne Exemple (pro) <jeanne@example.org>",
        "Jeanne Exemple <jeanne@example.net>",
    ]
    assert split_identity(identities[0]) == ("Jeanne Exemple", "jeanne@example.org")
    assert split_identity("<only@example.org>") == (None, "only@example.org")


@respx.mock
async def test_a_published_key_and_its_other_identities_are_found(
    http_client: httpx.AsyncClient,
) -> None:
    respx.get(url__startswith="https://keys.openpgp.org/pks/lookup").respond(200, text=INDEX)
    module = PgpKeys()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.EMAIL, "jeanne@example.org")
    )
    assert [(f.kind, f.value) for f in found] == [
        (EntityKind.URL, "https://keys.openpgp.org/search?q=jeanne%40example.org"),
        (EntityKind.NAME, "Jeanne Exemple"),
        (EntityKind.NAME, "Jeanne Exemple"),
        (EntityKind.EMAIL, "jeanne@example.net"),
    ]
    assert found[0].attributes["fingerprint"].startswith("0123")


@respx.mock
async def test_no_key_no_finding(http_client: httpx.AsyncClient) -> None:
    respx.get(url__startswith="https://keys.openpgp.org/pks/lookup").respond(404)
    module = PgpKeys()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.EMAIL, "jeanne@example.org")
    )
    assert found == []
