"""The Bluesky, GitLab, Stack Exchange, Hacker News, Keybase and Fediverse modules, against
recorded-style answers (no network)."""

import httpx
import pytest
import respx

from narcisse.domain import EntityKind
from narcisse.engine.plugin import InputRejected, RateLimited, SourceUnavailable, Target
from narcisse.modules.bluesky import Bluesky
from narcisse.modules.fediverse import INSTANCES, Fediverse
from narcisse.modules.github import GitHub
from narcisse.modules.gitlab import INSTANCES as GITLAB_INSTANCES
from narcisse.modules.gitlab import GitLab
from narcisse.modules.hackernews import HackerNews
from narcisse.modules.keybase import Keybase
from narcisse.modules.stackexchange import StackExchange
from narcisse.modules.whatsmyname import SITES
from narcisse.normalize import fold, normalize
from narcisse.preferences import Preferences
from tests.conftest import ApiFactory
from tests.module_context import FakeContext, run, target


def whatsmyname_url(site_name: str, username: str) -> str:
    """The address WhatsMyName gives for an account, normalized: a module finding the same
    account must give the same, so that both make one trace."""
    site = next(s for s in SITES if s.name == site_name)
    return normalize(EntityKind.ACCOUNT, site.url(site.pretty_url or site.check_url, username))[1]


def same_trace(url: str) -> str:
    return normalize(EntityKind.ACCOUNT, url)[1]


# Bluesky

BSKY = "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile"


@respx.mock
async def test_bluesky_reads_the_profile_of_a_username(http_client: httpx.AsyncClient) -> None:
    route = respx.get(url__startswith=BSKY).respond(
        200,
        json={
            "handle": "jeanne-exemple.bsky.social",
            "displayName": "Jeanne Exemple",
            "description": "Mon site : https://jeanne.example.org",
            "createdAt": "2024-02-01T10:00:00.000Z",
            "postsCount": 12,
        },
    )
    module = Bluesky()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.USERNAME, "Jeanne-Exemple")
    )

    assert route.calls.last.request.url.params["actor"] == "Jeanne-Exemple.bsky.social"
    assert [(f.kind, f.relation, f.value) for f in found] == [
        (EntityKind.ACCOUNT, "has_account", "https://bsky.app/profile/Jeanne-Exemple.bsky.social"),
        (EntityKind.NAME, "shows_name", "Jeanne Exemple"),
        (EntityKind.URL, "links_to", "https://jeanne.example.org"),
    ]
    assert same_trace(found[0].value) == whatsmyname_url("Bluesky Username", "Jeanne-Exemple")
    assert found[0].attributes["created"] == "2024-02-01"


@respx.mock
async def test_bluesky_takes_a_domain_handle_as_proof(http_client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=BSKY).respond(200, json={"handle": "jeanne.example.org"})
    module = Bluesky()
    by_domain = await run(
        module, FakeContext(module, http_client), target(EntityKind.DOMAIN, "jeanne.example.org")
    )
    assert [(f.kind, f.confidence) for f in by_domain] == [(EntityKind.ACCOUNT, 0.9)]

    # A username that is a full handle: the domain behind it is a trace of its own.
    by_name = await run(
        module,
        FakeContext(module, http_client),
        target(EntityKind.USERNAME, "jeanne.example.org"),
    )
    assert [(f.kind, f.relation) for f in by_name] == [
        (EntityKind.ACCOUNT, "has_account"),
        (EntityKind.DOMAIN, "handle_domain"),
    ]


@respx.mock
async def test_bluesky_finds_nothing_for_an_unknown_handle(http_client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=BSKY).respond(
        400, json={"error": "InvalidRequest", "message": "Profile not found"}
    )
    module = Bluesky()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.USERNAME, "personne")
    )
    assert found == []


def test_bluesky_takes_only_its_own_account_addresses() -> None:
    module = Bluesky()
    assert module.accepts_target(EntityKind.ACCOUNT, "https://bsky.app/profile/jeanne.bsky.social")
    assert not module.accepts_target(EntityKind.ACCOUNT, "https://github.com/jeanne")


# GitLab


def gitlab_user(host: str = "gitlab.com") -> dict[str, object]:
    return {
        "id": 42,
        "username": "jeanne-exemple",
        "name": "Jeanne Exemple",
        "public_email": "",
        "web_url": f"https://{host}/jeanne-exemple",
    }


def mock_gitlab_elsewhere_empty() -> None:
    for host in GITLAB_INSTANCES[1:]:
        respx.get(f"https://{host}/api/v4/users").respond(200, json=[])


@respx.mock
async def test_gitlab_finds_the_profile_and_the_addresses_of_pushed_commits(
    http_client: httpx.AsyncClient,
) -> None:
    mock_gitlab_elsewhere_empty()
    respx.get("https://gitlab.com/api/v4/users").respond(200, json=[gitlab_user()])
    details = respx.get("https://gitlab.com/api/v4/users/42").respond(403)
    respx.get(url__startswith="https://gitlab.com/api/v4/users/42/events").respond(
        200,
        json=[
            {"project_id": 7, "push_data": {"commit_to": "a1"}},
            {"project_id": 7, "push_data": {"commit_to": "a1"}},  # the same commit, asked once
            {"project_id": 7, "push_data": {"commit_to": "b2"}},
            {"project_id": 8, "push_data": {"commit_to": "c3"}},
            {"project_id": 9, "push_data": {"commit_to": None}},  # a deleted branch
        ],
    )
    commits = "https://gitlab.com/api/v4/projects/{}/repository/commits/{}"
    respx.get(commits.format(7, "a1")).respond(
        200,
        json={
            "author_name": "Jeanne Exemple",
            "author_email": "jeanne@example.org",
            "web_url": "https://gitlab.com/jeanne-exemple/notes/-/commit/a1",
        },
    )
    respx.get(commits.format(7, "b2")).respond(
        200, json={"author_name": "Paul Exemple", "author_email": "paul@example.org"}
    )
    respx.get(commits.format(8, "c3")).respond(
        200,
        json={
            "author_name": "jeanne-exemple",
            "author_email": "42-jeanne-exemple@users.noreply.gitlab.com",
        },
    )
    module = GitLab()
    ctx = FakeContext(module, http_client)
    found = await run(module, ctx, target(EntityKind.USERNAME, "Jeanne-Exemple"))

    assert [(f.kind, f.relation, f.value) for f in found] == [
        (EntityKind.ACCOUNT, "has_account", "https://gitlab.com/Jeanne-Exemple"),
        (EntityKind.NAME, "shows_name", "Jeanne Exemple"),
        # Paul's commit, pushed by Jeanne, isn't hers; the hidden address leaks nothing.
        (EntityKind.EMAIL, "commits_as", "jeanne@example.org"),
    ]
    assert same_trace(found[0].value) == whatsmyname_url("GitLab", "Jeanne-Exemple")
    assert not details.called  # gitlab.com shows details to signed-in clients only
    assert ctx.notes == {"checked": 5, "found": 1, "unreachable": 0}


@respx.mock
async def test_gitlab_reads_the_whole_profile_with_a_token(http_client: httpx.AsyncClient) -> None:
    mock_gitlab_elsewhere_empty()
    respx.get("https://gitlab.com/api/v4/users").respond(200, json=[gitlab_user()])
    details = respx.get("https://gitlab.com/api/v4/users/42").respond(
        200,
        json={
            **gitlab_user(),
            "location": "Lyon",
            "website_url": "jeanne.example.org",
            "linkedin": "jeanne-exemple",
            "bio": "Écrire à jeanne@example.net",
        },
    )
    respx.get(url__startswith="https://gitlab.com/api/v4/users/42/events").respond(200, json=[])
    module = GitLab()
    ctx = FakeContext(module, http_client, preferences=Preferences(gitlab_token="glpat-test"))
    found = await run(module, ctx, target(EntityKind.USERNAME, "jeanne-exemple"))

    assert details.calls.last.request.headers["PRIVATE-TOKEN"] == "glpat-test"
    assert [(f.kind, f.value) for f in found] == [
        (EntityKind.ACCOUNT, "https://gitlab.com/jeanne-exemple"),
        (EntityKind.NAME, "Jeanne Exemple"),
        (EntityKind.URL, "https://jeanne.example.org"),
        (EntityKind.ACCOUNT, "https://www.linkedin.com/in/jeanne-exemple"),
        (EntityKind.EMAIL, "jeanne@example.net"),
    ]
    assert found[0].attributes["location"] == "Lyon"


@respx.mock
async def test_gitlab_says_when_the_token_is_refused(http_client: httpx.AsyncClient) -> None:
    respx.get("https://gitlab.com/api/v4/users").respond(401)
    module = GitLab()
    ctx = FakeContext(module, http_client, preferences=Preferences(gitlab_token="expired"))
    with pytest.raises(SourceUnavailable, match="gitlab_token_rejected"):
        await run(module, ctx, target(EntityKind.USERNAME, "jeanne"))


@respx.mock
async def test_gitlab_goes_on_when_an_instance_is_unreachable(
    http_client: httpx.AsyncClient,
) -> None:
    mock_gitlab_elsewhere_empty()
    respx.get("https://gitlab.com/api/v4/users").mock(side_effect=httpx.ConnectError("down"))
    module = GitLab()
    ctx = FakeContext(module, http_client)
    assert await run(module, ctx, target(EntityKind.USERNAME, "jeanne")) == []
    assert ctx.notes == {"checked": 4, "found": 0, "unreachable": 1}


@respx.mock
async def test_gitlab_asks_only_the_instance_of_an_account(http_client: httpx.AsyncClient) -> None:
    route = respx.get("https://framagit.org/api/v4/users").respond(200, json=[])
    module = GitLab()
    assert module.accepts_target(EntityKind.ACCOUNT, "https://framagit.org/jeanne")
    assert not module.accepts_target(EntityKind.ACCOUNT, "https://framagit.org/jeanne/notes")
    await run(
        module,
        FakeContext(module, http_client),
        target(EntityKind.ACCOUNT, "https://framagit.org/jeanne"),
    )
    assert route.calls.last.request.url.params["username"] == "jeanne"
    assert len(respx.calls) == 1


# Stack Exchange

SE = "https://api.stackexchange.com/2.3"


def se_user(user_id: int, name: str, **extra: object) -> dict[str, object]:
    return {"user_id": user_id, "account_id": user_id * 10, "display_name": name, **extra}


@respx.mock
async def test_stack_exchange_keeps_only_the_same_name_and_its_network_accounts(
    http_client: httpx.AsyncClient,
) -> None:
    respx.get(f"{SE}/users").respond(
        200,
        json={
            "items": [
                se_user(
                    1,
                    "Jeanne Exemple",
                    location="Lyon",
                    website_url="https://jeanne.example.org",
                    about_me='<p>Contact : <a href="mailto:jeanne@example.org">écrire</a></p>',
                ),
                se_user(2, "Jeanne Exemple2"),
            ],
            "quota_remaining": 250,
        },
    )
    associated = respx.get(url__startswith=f"{SE}/users/10/associated").respond(
        200,
        json={
            "items": [
                {"site_url": "https://stackoverflow.com", "user_id": 1, "site_name": "SO"},
                {
                    "site_url": "https://superuser.com",
                    "user_id": 99,
                    "site_name": "Super User",
                },
            ]
        },
    )
    module = StackExchange()
    name = Target(
        entity_id=1, kind=EntityKind.NAME, value="Jeanne Exemple", normalized=fold("Jeanne Exemple")
    )
    found = await run(module, FakeContext(module, http_client), name)

    assert associated.called
    assert [(f.kind, f.value) for f in found] == [
        (EntityKind.ACCOUNT, "https://stackoverflow.com/users/1"),
        (EntityKind.URL, "https://jeanne.example.org"),
        (EntityKind.EMAIL, "jeanne@example.org"),
        (EntityKind.ACCOUNT, "https://superuser.com/users/99"),
    ]
    assert all(f.confidence == 0.3 for f in found)  # homonyms are common


@respx.mock
async def test_stack_exchange_leaves_the_network_out_for_homonyms(
    http_client: httpx.AsyncClient,
) -> None:
    respx.get(f"{SE}/users").respond(
        200, json={"items": [se_user(1, "jeanne"), se_user(3, "Jeanne")]}
    )
    module = StackExchange()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.USERNAME, "jeanne")
    )
    assert [f.value for f in found] == [
        "https://stackoverflow.com/users/1",
        "https://stackoverflow.com/users/3",
    ]
    assert len(respx.calls) == 1


@respx.mock
async def test_stack_exchange_out_of_quota_waits_for_the_next_day(
    http_client: httpx.AsyncClient,
) -> None:
    respx.get(f"{SE}/users").respond(
        400,
        json={"error_id": 502, "error_name": "throttle_violation", "error_message": "too many"},
    )
    module = StackExchange()
    with pytest.raises(RateLimited) as limited:
        await run(module, FakeContext(module, http_client), target(EntityKind.USERNAME, "jeanne"))
    assert 0 < limited.value.retry_after <= 86_400


# Hacker News

HN = "https://hacker-news.firebaseio.com/v0/user"


@respx.mock
async def test_hacker_news_reads_the_account_and_its_about(http_client: httpx.AsyncClient) -> None:
    respx.get(f"{HN}/Jeanne_Ex.json").respond(
        200,
        json={
            "id": "Jeanne_Ex",
            "created": 1_600_000_000,
            "karma": 12,
            "about": 'Site : <a href="https:&#x2F;&#x2F;jeanne.example.org">jeanne.example.org</a>'
            "<p>jeanne@example.org",
        },
    )
    module = HackerNews()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.USERNAME, "Jeanne_Ex")
    )
    assert [(f.kind, f.value) for f in found] == [
        (EntityKind.ACCOUNT, "https://news.ycombinator.com/user?id=Jeanne_Ex"),
        (EntityKind.URL, "https://jeanne.example.org"),
        (EntityKind.EMAIL, "jeanne@example.org"),
    ]
    assert same_trace(found[0].value) == whatsmyname_url("Hacker News", "Jeanne_Ex")
    assert found[0].attributes["created"] == "2020-09-13"


@respx.mock
async def test_hacker_news_finds_nothing_for_an_unknown_user(
    http_client: httpx.AsyncClient,
) -> None:
    respx.get(f"{HN}/personne.json").respond(200, text="null")
    module = HackerNews()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.USERNAME, "personne")
    )
    assert found == []
    assert not module.accepts_target(EntityKind.USERNAME, "jeanne.exemple")  # not a HN name


# Keybase

KEYBASE = "https://keybase.io/_/api/1.0/user/lookup.json"

KEYBASE_USER = {
    "id": "abc",
    "basics": {"username": "jeanne_ex"},
    "profile": {"full_name": "Jeanne Exemple", "location": "Lyon", "bio": None},
    "public_keys": {"primary": {"key_fingerprint": "ab" * 20}},  # a fictitious fingerprint
    "proofs_summary": {
        "all": [
            {
                "proof_type": "github",
                "nametag": "jeanne-exemple",
                "service_url": "https://github.com/jeanne-exemple",
                "proof_url": "https://gist.github.com/jeanne-exemple/1",
            },
            {
                "proof_type": "dns",
                "nametag": "jeanne.example.org",
                "service_url": "dns://jeanne.example.org",
                "proof_url": "dns://jeanne.example.org",
            },
        ]
    },
}


def keybase_answer(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    if params.get("usernames") == "Jeanne_Ex" or params.get("github") == "Jeanne_Ex":
        return httpx.Response(200, json={"status": {"code": 0}, "them": [KEYBASE_USER]})
    return httpx.Response(200, json={"status": {"code": 0}, "them": [None]})


@respx.mock
async def test_keybase_finds_the_account_and_what_its_proofs_link(
    http_client: httpx.AsyncClient,
) -> None:
    route = respx.get(url__startswith=KEYBASE).mock(side_effect=keybase_answer)
    module = Keybase()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.USERNAME, "Jeanne_Ex")
    )

    asked = [dict(c.request.url.params) for c in route.calls]
    assert [next(k for k in a if k != "fields") for a in asked] == [
        "usernames",
        "github",
        "twitter",
        "reddit",
        "hackernews",
    ]
    # The same user, found twice, is told once.
    assert [(f.kind, f.relation, f.value, f.confidence) for f in found] == [
        (EntityKind.ACCOUNT, "has_account", "https://keybase.io/Jeanne_Ex", 0.6),
        (EntityKind.NAME, "shows_name", "Jeanne Exemple", 0.5),
        (EntityKind.ACCOUNT, "proves", "https://github.com/jeanne-exemple", 0.9),
        (EntityKind.DOMAIN, "proves", "jeanne.example.org", 0.9),
    ]
    assert same_trace(found[0].value) == whatsmyname_url("Keybase", "Jeanne_Ex")
    assert found[0].attributes["pgp"] == "AB" * 20
    assert found[2].url == "https://gist.github.com/jeanne-exemple/1"
    # What the account shows and proves relates to the account.
    assert {f.via for f in found[1:]} == {(EntityKind.ACCOUNT, "https://keybase.io/Jeanne_Ex")}


@respx.mock
async def test_keybase_finds_who_proved_a_domain(http_client: httpx.AsyncClient) -> None:
    route = respx.get(url__startswith=KEYBASE).respond(
        200, json={"status": {"code": 0}, "them": [KEYBASE_USER]}
    )
    module = Keybase()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.DOMAIN, "jeanne.example.org")
    )
    assert route.calls.last.request.url.params["domain"] == "jeanne.example.org"
    # The domain's own proof isn't told again.
    assert [(f.kind, f.value, f.confidence) for f in found] == [
        (EntityKind.ACCOUNT, "https://keybase.io/jeanne_ex", 0.9),
        (EntityKind.NAME, "Jeanne Exemple", 0.5),
        (EntityKind.ACCOUNT, "https://github.com/jeanne-exemple", 0.9),
    ]


@respx.mock
async def test_keybase_skips_values_it_cannot_take(http_client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=KEYBASE).respond(
        200, json={"status": {"code": 100, "name": "INPUT_ERROR"}}
    )
    module = Keybase()
    found = await run(
        module, FakeContext(module, http_client), target(EntityKind.USERNAME, "jeanne.exemple")
    )
    assert found == []


# Fediverse

MASTODON_ACCOUNT = {
    "username": "jeanne",
    "display_name": "Jeanne Exemple",
    "created_at": "2022-11-05T00:00:00.000Z",
    "note": '<p>Bonjour ! Avec <a href="https://social.example/@paul" class="u-url mention">'
    "@paul</a></p>",
    "fields": [
        {
            "name": "Site",
            "value": '<a href="https://jeanne.example.org" rel="me">jeanne.example.org</a>',
            "verified_at": "2023-01-01T00:00:00.000+00:00",
        },
        {
            "name": "Code",
            "value": '<a href="https://github.com/jeanne-exemple">github.com/jeanne-exemple</a>',
            "verified_at": None,
        },
    ],
}


def lookup(host: str) -> str:
    return f"https://{host}/api/v1/accounts/lookup"


@respx.mock
async def test_fediverse_looks_on_every_listed_instance(http_client: httpx.AsyncClient) -> None:
    for host in INSTANCES[2:]:
        respx.get(url__startswith=lookup(host)).respond(404, json={"error": "Record not found"})
    respx.get(url__startswith=lookup(INSTANCES[0])).respond(200, json=MASTODON_ACCOUNT)
    respx.get(url__startswith=lookup(INSTANCES[1])).mock(side_effect=httpx.ConnectError("down"))
    added = respx.get(url__startswith=lookup("social.example.org")).respond(404)
    module = Fediverse()
    ctx = FakeContext(
        module, http_client, preferences=Preferences(fediverse_instances=("social.example.org",))
    )
    found = await run(module, ctx, target(EntityKind.USERNAME, "jeanne"))

    assert added.called  # the user's own instance too
    assert ctx.notes == {"checked": len(INSTANCES), "found": 1, "unreachable": 1}
    assert [(f.kind, f.value, f.confidence) for f in found] == [
        (EntityKind.ACCOUNT, "https://mastodon.social/@jeanne", 0.5),
        (EntityKind.NAME, "Jeanne Exemple", 0.5),
        # A verified link is the owner's; a mention in the bio is someone else.
        (EntityKind.URL, "https://jeanne.example.org", 0.9),
        (EntityKind.ACCOUNT, "https://github.com/jeanne-exemple", 0.6),
    ]
    assert same_trace(found[0].value) == whatsmyname_url("Mastodon-mastodon", "jeanne")


@respx.mock
async def test_a_fediverse_handle_is_asked_on_its_own_instance_once_listed(
    http_client: httpx.AsyncClient,
) -> None:
    module = Fediverse()
    handle = target(EntityKind.USERNAME, "jeanne@social.example.org")
    with pytest.raises(InputRejected, match="instance_not_listed"):
        await run(module, FakeContext(module, http_client), handle)

    route = respx.get(url__startswith=lookup("social.example.org")).respond(
        200, json=MASTODON_ACCOUNT
    )
    preferences = Preferences(fediverse_instances=("social.example.org",))
    found = await run(module, FakeContext(module, http_client, preferences=preferences), handle)
    assert len(respx.calls) == 1
    assert route.calls.last.request.url.params["acct"] == "jeanne"
    assert (found[0].value, found[0].confidence) == ("https://social.example.org/@jeanne", 0.9)


@respx.mock
async def test_fediverse_falls_back_on_webfinger_and_activitypub(
    http_client: httpx.AsyncClient,
) -> None:
    host = "social.example.org"
    respx.get(url__startswith=lookup(host)).respond(401)
    respx.get(url__startswith=f"https://{host}/.well-known/webfinger").respond(
        200,
        json={
            "links": [
                {
                    "rel": "self",
                    "type": "application/activity+json",
                    "href": f"https://{host}/users/jeanne",
                },
                {"rel": "http://webfinger.net/rel/profile-page", "href": f"https://{host}/@jeanne"},
            ]
        },
    )
    actor = respx.get(f"https://{host}/users/jeanne").respond(
        200,
        json={
            "name": "Jeanne",
            "summary": "<p>jeanne@example.org</p>",
            "attachment": [
                {"type": "PropertyValue", "name": "Site", "value": "https://jeanne.example.org"}
            ],
        },
    )
    module = Fediverse()
    preferences = Preferences(fediverse_instances=(host,))
    found = await run(
        module,
        FakeContext(module, http_client, preferences=preferences),
        target(EntityKind.ACCOUNT, f"https://{host}/@jeanne"),
    )
    assert actor.calls.last.request.headers["Accept"] == "application/activity+json"
    # An account given as the seed isn't told again; what its profile shows is.
    assert [(f.kind, f.value) for f in found] == [
        (EntityKind.NAME, "Jeanne"),
        (EntityKind.EMAIL, "jeanne@example.org"),
        (EntityKind.URL, "https://jeanne.example.org"),
    ]


def test_a_fediverse_handle_goes_to_the_fediverse_module_only() -> None:
    assert Fediverse().accepts_target(EntityKind.USERNAME, "jeanne@social.example.org")
    assert Fediverse().accepts_target(EntityKind.ACCOUNT, "https://social.example.org/@jeanne")
    assert not Fediverse().accepts_target(EntityKind.ACCOUNT, "https://example.org/jeanne")
    assert not GitHub().accepts_target(EntityKind.USERNAME, "jeanne@social.example.org")
    assert GitHub().accepts_target(EntityKind.USERNAME, "jeanne")


async def test_a_scan_gives_each_seed_to_the_sources_that_can_use_it(
    make_api: ApiFactory,
) -> None:
    api = await make_api({"github": GitHub(), "fediverse": Fediverse(), "bluesky": Bluesky()})
    profile = await api.profile(
        ("username", "@jeanne@social.example.org"),
        ("account", "https://github.com/jeanne-exemple"),
    )
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    done = await api.wait_scan(scan["id"], lambda s: s["status"] == "done")

    # A handle is a Fediverse thing; a GitHub address, nobody's here (no source reads it).
    assert [(r["module"], r["input_value"]) for r in done["runs"]] == [
        ("fediverse", "jeanne@social.example.org")
    ]
    assert done["runs"][0]["error_code"] == "instance_not_listed"
    assert done["runs"][0]["error_params"] == {"host": "social.example.org"}
