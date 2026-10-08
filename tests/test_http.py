"""The HTTP client modules use: pacing, rate limits, errors, declared hosts, robots.txt."""

from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from narcisse.clock import Clock
from narcisse.engine.http import USER_AGENT, DomainPacer, HttpClient, new_transport_client
from narcisse.engine.plugin import ModuleMeta, RateLimit, RateLimited, TransientError
from tests.fakes import meta

SOURCE = ModuleMeta(
    **{
        **vars(meta("test.source")),
        "hosts": ("api.example.org", "www.example.org"),
        "rate_limit": RateLimit(requests=2, per_seconds=10),
    }
)


@pytest.fixture
def clock() -> Clock:
    return Clock(speed=1000)


@pytest.fixture
async def http(clock: Clock) -> AsyncIterator[HttpClient]:
    async with new_transport_client() as client:
        yield HttpClient(client, DomainPacer(clock), SOURCE, clock)


@respx.mock
async def test_requests_say_who_they_are(http: HttpClient) -> None:
    route = respx.get("https://api.example.org/u/jeanne").respond(200, json={})
    await http.get("https://api.example.org/u/jeanne")
    assert route.calls.last.request.headers["User-Agent"] == USER_AGENT
    assert "github.com/j3ffx/narcisse" in USER_AGENT


async def test_an_undeclared_host_is_a_bug(http: HttpClient) -> None:
    with pytest.raises(ValueError, match="may not contact"):
        await http.get("https://elsewhere.example.net/")


@respx.mock
async def test_requests_to_a_domain_are_spaced_out(http: HttpClient, clock: Clock) -> None:
    respx.get(host="api.example.org").respond(200)
    started = clock.now()
    for _ in range(3):
        await http.get("https://api.example.org/")
    # 2 requests per 10 s: the third waits for two intervals of 5 s.
    assert (clock.now() - started).total_seconds() >= 10


@respx.mock
async def test_a_429_blocks_the_domain_for_every_run(http: HttpClient) -> None:
    respx.get("https://api.example.org/a").respond(429, headers={"Retry-After": "120"})
    with pytest.raises(RateLimited) as limited:
        await http.get("https://api.example.org/a")
    assert limited.value.retry_after == 120
    assert limited.value.params == {"host": "api.example.org"}
    # The next request doesn't even knock.
    with pytest.raises(RateLimited) as again:
        await http.get("https://api.example.org/b")
    assert 0 < again.value.retry_after <= 120
    assert len(respx.calls) == 1


@respx.mock
async def test_a_dated_retry_after_is_understood(http: HttpClient) -> None:
    respx.get("https://api.example.org/").respond(
        503, headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}
    )
    with pytest.raises(RateLimited) as limited:
        await http.get("https://api.example.org/")
    assert limited.value.retry_after == 0  # already past


@respx.mock
async def test_server_and_network_errors_are_transient(http: HttpClient) -> None:
    respx.get("https://api.example.org/500").respond(502)
    respx.get("https://api.example.org/down").mock(side_effect=httpx.ConnectError("refused"))
    respx.get("https://api.example.org/slow").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(TransientError) as error:
        await http.get("https://api.example.org/500")
    assert (error.value.code, error.value.params["status"]) == ("source_error", 502)
    with pytest.raises(TransientError, match="network_error"):
        await http.get("https://api.example.org/down")
    with pytest.raises(TransientError, match="source_timeout"):
        await http.get("https://api.example.org/slow")


@respx.mock
async def test_robots_txt_is_honoured_and_read_once(http: HttpClient) -> None:
    robots = respx.get("https://www.example.org/robots.txt").respond(
        200, text="User-agent: *\nDisallow: /private/\n"
    )
    assert await http.allowed_by_robots("https://www.example.org/public/jeanne")
    assert not await http.allowed_by_robots("https://www.example.org/private/jeanne")
    assert robots.call_count == 1


@respx.mock
@pytest.mark.parametrize(("status", "allowed"), [(404, True), (403, False)])
async def test_a_missing_or_forbidden_robots_txt(
    http: HttpClient, status: int, allowed: bool
) -> None:
    respx.get("https://www.example.org/robots.txt").respond(status)
    assert await http.allowed_by_robots("https://www.example.org/jeanne") is allowed
