"""The accounts-by-username module (WhatsMyName list)."""

from dataclasses import replace
from urllib.parse import urlsplit

import httpx
import respx

from narcisse.domain import EntityKind
from narcisse.engine.http import USER_AGENT, host_declared
from narcisse.modules.whatsmyname import (
    SITES,
    Site,
    Verdict,
    WhatsMyName,
    host_pattern,
    judge,
)
from narcisse.preferences import Preferences
from tests.module_context import FakeContext, run, target


def site(name: str, url: str, **overrides: object) -> Site:
    values: dict[str, object] = {
        "name": name,
        "check_url": url,
        "pretty_url": None,
        "body": None,
        "headers": {},
        "exists_code": 200,
        "exists_text": "profile-of",
        "missing_code": 404,
        "missing_text": "",
        "category": "social",
        "strip_chars": "",
        "protection": frozenset(),
    }
    values.update(overrides)
    return Site(**values)  # type: ignore[arg-type]


def module(*sites: Site) -> WhatsMyName:
    """The module on these test sites only (and their hosts only)."""

    class OnTheseSites(WhatsMyName):
        meta = replace(WhatsMyName.meta, hosts=tuple(host_pattern(s.check_url) for s in sites))

    return OnTheseSites(list(sites))


def test_the_list_is_usable_and_every_host_is_declared() -> None:
    assert len(SITES) > 600
    hosts = WhatsMyName.meta.hosts
    for s in SITES:
        url = s.url(s.check_url, "jeanne")
        assert host_declared(urlsplit(url).hostname or "", hosts), s.name
        assert "api_key=" not in s.check_url, s.name
        assert "client_id=" not in s.check_url, s.name
        assert not {h.lower() for h in s.headers} - {"accept", "accept-language", "content-type"}


def test_verdicts_follow_the_list_rules() -> None:
    s = site("Forum", "https://forum.example.org/u/{account}", missing_text="no such user")
    assert judge(s, 200, {}, "<div class=profile-of>") == Verdict.FOUND
    assert judge(s, 404, {}, "no such user") == Verdict.MISSING
    assert judge(s, 200, {}, "something else") == Verdict.UNCERTAIN
    assert judge(s, 403, {"cf-mitigated": "challenge"}, "") == Verdict.BLOCKED
    assert judge(s, 503, {}, "<title>Just a moment...</title>") == Verdict.BLOCKED


def test_a_username_in_the_host_becomes_a_wildcard() -> None:
    assert host_pattern("https://{account}.blog.example.net/") == "*.blog.example.net"
    assert host_pattern("https://example.net/u/{account}") == "example.net"


@respx.mock
async def test_accounts_are_found_and_the_run_reports_what_it_could_not_tell(
    http_client: httpx.AsyncClient,
) -> None:
    sites = [
        site("Forum", "https://forum.example.org/u/{account}"),
        site(
            "Photos",
            "https://photos.example.net/{account}",
            pretty_url="https://photos.example.net/@{account}",
        ),
        site("Musique", "https://musique.example.com/{account}"),
        site("Code", "https://code.example.org/{account}"),
        site("Panne", "https://down.example.net/{account}"),
        site("Captcha", "https://captcha.example.org/{account}", protection=frozenset({"captcha"})),
        site("Adulte", "https://adult.example.com/{account}", category="xx NSFW xx"),
    ]
    respx.get("https://forum.example.org/u/jeanne.exemple").respond(200, text="profile-of")
    respx.get("https://photos.example.net/jeanne.exemple").respond(200, text="profile-of")
    respx.get("https://musique.example.com/jeanne.exemple").respond(404)
    respx.get("https://code.example.org/jeanne.exemple").respond(
        403, headers={"cf-mitigated": "challenge"}
    )
    respx.get("https://down.example.net/jeanne.exemple").respond(500)
    m = module(*sites)
    ctx = FakeContext(m, http_client, preferences=Preferences(exclude_adult=True))

    found = await run(m, ctx, target(EntityKind.USERNAME, "jeanne.exemple"))

    assert sorted(f.value for f in found) == [
        "https://forum.example.org/u/jeanne.exemple",
        "https://photos.example.net/@jeanne.exemple",  # the readable address when the list has one
    ]
    assert found[0].attributes["adult"] is False
    assert ctx.notes == {
        "skipped": 1,
        "excluded": 1,
        "checked": 4,
        "found": 2,
        "blocked": 1,
        "unreachable": 1,
    }
    assert not any(c.request.url.host == "captcha.example.org" for c in respx.calls)


@respx.mock
async def test_adult_sites_are_checked_and_labelled_unless_excluded(
    http_client: httpx.AsyncClient,
) -> None:
    m = module(site("Adulte", "https://adult.example.com/{account}", category="xx NSFW xx"))
    respx.get("https://adult.example.com/jeanne").respond(200, text="profile-of")
    [finding] = await run(m, FakeContext(m, http_client), target(EntityKind.USERNAME, "jeanne"))
    assert finding.attributes["adult"] is True
    assert "(site adulte)" in (finding.excerpt or "")


@respx.mock
async def test_only_neutral_headers_are_sent_and_the_user_agent_stays_honest(
    http_client: httpx.AsyncClient,
) -> None:
    raw = site(
        "Api",
        "https://api.example.org/users/{account}",
        headers={"Accept": "application/json"},
    )
    m = module(raw)
    route = respx.get("https://api.example.org/users/jeanne").respond(200, text="profile-of")
    await run(m, FakeContext(m, http_client), target(EntityKind.USERNAME, "jeanne"))
    sent = route.calls.last.request.headers
    assert sent["User-Agent"] == USER_AGENT
    assert sent["Accept"] == "application/json"


@respx.mock
async def test_an_unexpected_redirect_is_followed_once(http_client: httpx.AsyncClient) -> None:
    m = module(site("Moved", "http://moved.example.org/{account}"))
    respx.get("http://moved.example.org/jeanne").respond(
        301, headers={"Location": "https://moved.example.org/jeanne"}
    )
    respx.get("https://moved.example.org/jeanne").respond(200, text="profile-of")
    found = await run(m, FakeContext(m, http_client), target(EntityKind.USERNAME, "jeanne"))
    assert len(found) == 1


@respx.mock
async def test_a_redirect_the_list_expects_means_missing(http_client: httpx.AsyncClient) -> None:
    m = module(site("Gone", "https://gone.example.org/{account}", missing_code=302))
    route = respx.get("https://gone.example.org/jeanne").respond(
        302, headers={"Location": "https://gone.example.org/"}
    )
    ctx = FakeContext(m, http_client)
    assert await run(m, ctx, target(EntityKind.USERNAME, "jeanne")) == []
    assert route.call_count == 1
    assert ctx.notes == {"checked": 1}


@respx.mock
async def test_a_resumed_run_skips_the_sites_already_checked(
    http_client: httpx.AsyncClient,
) -> None:
    m = module(
        site("Forum", "https://forum.example.org/u/{account}"),
        site("Photos", "https://photos.example.net/{account}"),
    )
    respx.get("https://photos.example.net/jeanne").respond(404)
    ctx = FakeContext(
        m, http_client, checkpoint={"done": ["Forum"], "notes": {"checked": 1, "found": 1}}
    )
    await run(m, ctx, target(EntityKind.USERNAME, "jeanne"))
    assert [c.request.url.host for c in respx.calls] == ["photos.example.net"]
    assert ctx.notes == {"checked": 2, "found": 1}
    assert ctx.progressed[-1] == (2, 2)
