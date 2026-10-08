"""HTTP for modules: honest User-Agent, per-domain pacing, robots.txt, errors the UI can explain."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from narcisse import __version__
from narcisse.clock import Clock
from narcisse.engine.plugin import ModuleMeta, RateLimited, TransientError

USER_AGENT = f"Narcisse/{__version__} (self-OSINT tool; +https://github.com/j3ffx/narcisse)"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)
# Without a Retry-After header, a 429 means "come back in a minute".
DEFAULT_RETRY_AFTER = 60.0


def new_transport_client(**kwargs: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True,
        **kwargs,
    )


class DomainPacer:
    """Spaces requests per domain, across every run and module, and remembers a domain's
    "come back later" so that other runs don't knock in the meantime."""

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self._next_slot: dict[str, datetime] = {}
        self._blocked: dict[str, datetime] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def blocked_until(self, host: str) -> datetime | None:
        moment = self._blocked.get(host)
        return moment if moment and moment > self.clock.now() else None

    def block(self, host: str, seconds: float) -> None:
        until = self.clock.now() + timedelta(seconds=seconds)
        self._blocked[host] = max(until, self._blocked.get(host, until))

    async def wait_turn(self, host: str, interval: float) -> None:
        async with self._locks[host]:
            moment = self._next_slot.get(host)
            if moment is not None:
                await self.clock.sleep(self.clock.seconds_until(moment))
            self._next_slot[host] = self.clock.now() + timedelta(seconds=interval)


def _retry_after(response: httpx.Response, clock: Clock) -> float:
    value = response.headers.get("Retry-After")
    if value is None:
        return DEFAULT_RETRY_AFTER
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, clock.seconds_until(parsedate_to_datetime(value)))
        except (TypeError, ValueError):
            return DEFAULT_RETRY_AFTER


class HttpClient:
    """The client a module uses. Only the hosts its metadata declares are reachable."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        pacer: DomainPacer,
        meta: ModuleMeta,
        clock: Clock,
    ) -> None:
        self._client = client
        self._pacer = pacer
        self._meta = meta
        self._clock = clock
        self._robots: dict[str, RobotFileParser] = {}

    def _host(self, url: str) -> str:
        host = urlsplit(url).hostname or ""
        if host not in self._meta.hosts:
            # A module reaching an undeclared host is a bug: the list of hosts is a promise.
            raise ValueError(f"{self._meta.name} may not contact {host!r}")
        return host

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        host = self._host(url)
        if blocked := self._pacer.blocked_until(host):
            raise RateLimited(self._clock.seconds_until(blocked), host=host)
        interval = self._meta.rate_limit.interval if self._meta.rate_limit else 0.0
        await self._pacer.wait_turn(host, interval)
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise TransientError("source_timeout", host=host) from exc
        except httpx.TransportError as exc:
            raise TransientError("network_error", host=host) from exc
        if response.status_code == 429 or (
            response.status_code == 503 and "Retry-After" in response.headers
        ):
            wait = _retry_after(response, self._clock)
            self._pacer.block(host, wait)
            raise RateLimited(wait, host=host)
        if response.status_code >= 500:
            raise TransientError("source_error", host=host, status=response.status_code)
        return response

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def allowed_by_robots(self, url: str) -> bool:
        """Whether robots.txt lets Narcisse crawl `url` (for page crawling, not for APIs)."""
        parts = urlsplit(url)
        host = self._host(url)
        parser = self._robots.get(host)
        if parser is None:
            parser = RobotFileParser()
            response = await self.get(f"{parts.scheme}://{parts.netloc}/robots.txt")
            if response.status_code in (401, 403):
                parser.parse(["User-agent: *", "Disallow: /"])
            elif response.status_code >= 400:
                parser.parse([])  # no robots.txt: everything is allowed
            else:
                parser.parse(response.text.splitlines())
            self._robots[host] = parser
        return parser.can_fetch(USER_AGENT, url)
