"""The light-active e-mail checks, each against mocked answers (respx, no network).

Per module: a registered address yields one ACCOUNT trace ("registered_on" the service), an
unknown address yields nothing, and an unreadable answer (an anti-bot page, a moved endpoint)
yields nothing and is reported as "couldn't tell" — never a false positive. CI never asks a real
service, and no real address is used.
"""

import httpx
import pytest
import respx

from narcisse.domain import EntityKind
from narcisse.engine.plugin import Finding, SourceModule
from narcisse.modules.codepen import CodePen
from narcisse.modules.docker import Docker
from narcisse.modules.firefox import Firefox
from narcisse.modules.github_signup import GitHubSignup
from narcisse.modules.lastfm import LastFm
from narcisse.modules.pinterest import Pinterest
from narcisse.modules.quora import Quora
from narcisse.modules.rocketreach import RocketReach
from narcisse.modules.soundcloud import SoundCloud
from narcisse.modules.strava import Strava
from tests.module_context import FakeContext, run, target

ADDR = "jeanne@example.org"


async def check(module: SourceModule, http_client: httpx.AsyncClient) -> list[Finding]:
    return await run(module, FakeContext(module, http_client), target(EntityKind.EMAIL, ADDR))


def assert_registered(module: SourceModule, found: list[Finding]) -> None:
    assert [(f.kind, f.relation, f.value, f.confidence) for f in found] == [
        (EntityKind.ACCOUNT, "registered_on", module.account_url, 0.5)
    ]


# Firefox


@respx.mock
async def test_firefox(http_client: httpx.AsyncClient) -> None:
    route = respx.post("https://api.accounts.firefox.com/v1/account/status")
    route.respond(200, json={"exists": True})
    assert_registered(Firefox(), await check(Firefox(), http_client))
    route.respond(200, json={"exists": False})
    assert await check(Firefox(), http_client) == []
    route.respond(200, text="<html>anti-bot</html>")
    assert await check(Firefox(), http_client) == []


# Docker


@respx.mock
async def test_docker(http_client: httpx.AsyncClient) -> None:
    route = respx.post("https://hub.docker.com/v2/users/signup/")
    route.respond(400, json={"email": ["This email is already in use."]})
    assert_registered(Docker(), await check(Docker(), http_client))
    route.respond(400, json={"password": ["This field may not be blank."]})
    assert await check(Docker(), http_client) == []
    route.respond(200, text="<html>challenge</html>")
    assert await check(Docker(), http_client) == []


# RocketReach


@respx.mock
async def test_rocketreach(http_client: httpx.AsyncClient) -> None:
    respx.get("https://rocketreach.co/signup").respond(
        200, text='<input name="csrfmiddlewaretoken" value="tok">'
    )
    route = respx.get(url__startswith="https://rocketreach.co/v1/validateEmail")
    route.respond(200, json={"found": True})
    assert_registered(RocketReach(), await check(RocketReach(), http_client))
    route.respond(200, json={"found": False})
    assert await check(RocketReach(), http_client) == []
    route.respond(200, text="nope")
    assert await check(RocketReach(), http_client) == []


# Last.fm


@respx.mock
async def test_lastfm(http_client: httpx.AsyncClient) -> None:
    respx.get("https://www.last.fm/join").respond(
        200, headers={"set-cookie": "csrftoken=tok; Path=/"}
    )
    route = respx.post("https://www.last.fm/join/partial/validate")
    route.respond(
        200,
        json={"email": {"error_messages": ["Sorry, that email address is already registered."]}},
    )
    assert_registered(LastFm(), await check(LastFm(), http_client))
    route.respond(200, json={"email": {"error_messages": ["Please enter a valid email address."]}})
    assert await check(LastFm(), http_client) == []


@respx.mock
async def test_lastfm_without_a_token_cannot_tell(http_client: httpx.AsyncClient) -> None:
    respx.get("https://www.last.fm/join").respond(200, text="no cookie here")
    assert await check(LastFm(), http_client) == []


# CodePen


@respx.mock
async def test_codepen(http_client: httpx.AsyncClient) -> None:
    respx.get("https://codepen.io/accounts/signup/user/free").respond(
        200, text='<meta name="csrf-token" content="tok">'
    )
    route = respx.post("https://codepen.io/accounts/duplicate_check")
    route.respond(200, text="That Email is already taken.")
    assert_registered(CodePen(), await check(CodePen(), http_client))
    route.respond(200, text="That Email is available.")
    assert await check(CodePen(), http_client) == []


# Strava


@respx.mock
async def test_strava(http_client: httpx.AsyncClient) -> None:
    respx.get("https://www.strava.com/register/free").respond(
        200, text='<meta name="csrf-token" content="tok">'
    )
    route = respx.get(url__startswith="https://www.strava.com/athletes/email_unique")
    route.respond(200, text="false")  # not unique → registered
    assert_registered(Strava(), await check(Strava(), http_client))
    route.respond(200, text="true")  # unique → free
    assert await check(Strava(), http_client) == []
    route.respond(200, text="<html>challenge</html>")
    assert await check(Strava(), http_client) == []


# Quora


@respx.mock
async def test_quora(http_client: httpx.AsyncClient) -> None:
    respx.get("https://fr.quora.com").respond(200, text='formkey": "tok"')
    route = respx.post("https://fr.quora.com/webnode2/server_call_POST")
    route.respond(200, text="Un compte a déjà cette adresse")
    assert_registered(Quora(), await check(Quora(), http_client))
    route.respond(200, text="ok")
    assert await check(Quora(), http_client) == []


@respx.mock
async def test_quora_without_a_formkey_cannot_tell(http_client: httpx.AsyncClient) -> None:
    respx.get("https://fr.quora.com").respond(200, text="<html>no key</html>")
    assert await check(Quora(), http_client) == []


# SoundCloud


@respx.mock
async def test_soundcloud(http_client: httpx.AsyncClient) -> None:
    respx.get("https://soundcloud.com/").respond(200, text='window={"clientId":"abc123"}')
    route = respx.get(url__startswith="https://api-auth.soundcloud.com/web-auth/identifier")
    route.respond(200, json={"status": "in_use"})
    assert_registered(SoundCloud(), await check(SoundCloud(), http_client))
    route.respond(200, json={"status": "available"})
    assert await check(SoundCloud(), http_client) == []


# Pinterest


@respx.mock
async def test_pinterest(http_client: httpx.AsyncClient) -> None:
    route = respx.get(
        url__startswith="https://www.pinterest.com/_ngjs/resource/EmailExistsResource/get/"
    )
    route.respond(200, json={"resource_response": {"data": True}})
    assert_registered(Pinterest(), await check(Pinterest(), http_client))
    route.respond(200, json={"resource_response": {"data": False}})
    assert await check(Pinterest(), http_client) == []
    route.respond(200, json={"resource_response": {"data": {"source_field": "email"}}})
    assert await check(Pinterest(), http_client) == []


# GitHub (sign-up)

SIGNUP_PAGE = (
    '<auto-check src="/signup_check/email" csrf="x">'
    '<input name="authenticity_token" value="tok"></auto-check>'
)


@respx.mock
async def test_github_signup(http_client: httpx.AsyncClient) -> None:
    respx.get("https://github.com/signup").respond(200, text=SIGNUP_PAGE)
    route = respx.post("https://github.com/signup_check/email")
    route.respond(422, text="already taken")
    assert_registered(GitHubSignup(), await check(GitHubSignup(), http_client))
    route.respond(200, text="ok")
    assert await check(GitHubSignup(), http_client) == []
    route.respond(200, text="Your browser did something unexpected.")
    assert await check(GitHubSignup(), http_client) == []


# The whole set reports a clean note for every outcome.


@respx.mock
@pytest.mark.parametrize("payload", [{"exists": True}, {"exists": False}, None])
async def test_the_note_names_the_outcome(
    http_client: httpx.AsyncClient, payload: dict[str, bool] | None
) -> None:
    route = respx.post("https://api.accounts.firefox.com/v1/account/status")
    route.respond(200, json=payload) if payload else route.respond(200, text="<html>x</html>")
    module = Firefox()
    ctx = FakeContext(module, http_client)
    await run(module, ctx, target(EntityKind.EMAIL, ADDR))
    if payload == {"exists": True}:
        expected = {"found": 1}
    elif payload == {"exists": False}:
        expected = {"checked": 1}
    else:
        expected = {"uncertain": 1}
    assert ctx.notes == expected
