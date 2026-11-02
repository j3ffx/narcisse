"""The check for a new version: nothing leaves unless the user ticked the box."""

import httpx
import pytest

from narcisse import __version__
from narcisse.api.updates import RELEASES, newer
from tests.conftest import Api, ApiFactory


class GitHub(httpx.AsyncBaseTransport):
    def __init__(self, status: int = 200, body: object | None = None) -> None:
        self.status = status
        self.body = {"tag_name": "v99.0.0"} if body is None else body
        self.asked: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.asked.append(request)
        return httpx.Response(self.status, json=self.body)


async def ticked(make_api: ApiFactory, github: GitHub) -> Api:
    api = await make_api(demo=False, http_transport=github)
    await api.json("PATCH", "/preferences", {"check_updates": True})
    return api


@pytest.mark.parametrize(
    ("tag", "current", "expected"),
    [
        ("v0.6.0", "0.5.0", "0.6.0"),
        ("v0.10.0", "0.9.0", "0.10.0"),  # numbers, not text
        ("v0.5.0", "0.5.0", None),
        ("v0.4.0", "0.5.0", None),
        ("v1.0.0-rc.1", "0.5.0", None),
        ("<script>", "0.5.0", None),
        (None, "0.5.0", None),
    ],
)
def test_only_a_later_version_counts(tag: object, current: str, expected: str | None) -> None:
    assert newer(tag, current) == expected


async def test_nothing_leaves_until_the_box_is_ticked(make_api: ApiFactory) -> None:
    github = GitHub()
    api = await make_api(demo=False, http_transport=github)
    assert (await api.json("GET", "/preferences"))["check_updates"] is False
    assert await api.json("GET", "/update") == {"latest": None, "url": None}
    assert github.asked == []


async def test_a_later_version_is_told_with_a_link_of_our_own(make_api: ApiFactory) -> None:
    github = GitHub(body={"tag_name": "v99.0.0", "html_url": "https://hostile.example.org/"})
    api = await ticked(make_api, github)
    assert await api.json("GET", "/update") == {"latest": "99.0.0", "url": RELEASES}
    [request] = github.asked
    assert request.url.host == "api.github.com"
    assert request.content == b""
    assert "Narcisse/" in request.headers["user-agent"]


async def test_github_is_asked_at_most_once_a_day(make_api: ApiFactory) -> None:
    github = GitHub()
    api = await ticked(make_api, github)
    for _ in range(3):
        await api.json("GET", "/update")
    assert len(github.asked) == 1


async def test_the_same_version_tells_nothing(make_api: ApiFactory) -> None:
    api = await ticked(make_api, GitHub(body={"tag_name": f"v{__version__}"}))
    assert (await api.json("GET", "/update"))["latest"] is None


@pytest.mark.parametrize(("status", "body"), [(403, {}), (200, ["not", "a", "release"])])
async def test_a_failure_stays_silent(make_api: ApiFactory, status: int, body: object) -> None:
    api = await ticked(make_api, GitHub(status, body))
    assert (await api.json("GET", "/update"))["latest"] is None


async def test_demo_mode_never_asks(make_api: ApiFactory) -> None:
    github = GitHub()
    api = await make_api(demo=True, http_transport=github)
    await api.json("PATCH", "/preferences", {"check_updates": True})
    assert (await api.json("GET", "/update"))["latest"] is None
    assert github.asked == []
