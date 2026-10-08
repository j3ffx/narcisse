"""Keeps the local server for the local user.

Any website open in the browser can send requests to 127.0.0.1. Three rules stop it from reading
or changing anything:
- the `Host` must be loopback (127.0.0.1, ::1, localhost or a *.localhost name, which browsers
  resolve themselves), which defeats DNS rebinding (a hostile name resolving to 127.0.0.1);
- a state-changing request must come from Narcisse's own origin (or carry none: curl, scripts);
- its body must be JSON, which a cross-site form can't send without a CORS preflight, and no CORS
  header is ever granted.
"""

import json

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def hostname_of(host_header: str) -> str:
    if host_header.startswith("["):  # [::1]:8765
        return host_header[1 : host_header.find("]")]
    return host_header.rsplit(":", 1)[0] if host_header.count(":") == 1 else host_header


class LocalOnlyMiddleware:
    def __init__(self, app: ASGIApp, *, allowed_origins: frozenset[str]) -> None:
        self.app = app
        self.allowed_origins = allowed_origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        problem = self._problem(scope["method"], headers)
        if problem is None:
            await self.app(scope, receive, send)
            return
        status, code = problem
        body = json.dumps({"code": code, "params": {}}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    def _problem(self, method: str, headers: Headers) -> tuple[int, str] | None:
        hostname = hostname_of(headers.get("host", "")).lower()
        if hostname not in LOOPBACK_HOSTS and not hostname.endswith(".localhost"):
            return 403, "forbidden_host"
        if method in SAFE_METHODS:
            return None
        origin = headers.get("origin")
        if origin is not None and origin not in self.allowed_origins:
            return 403, "forbidden_origin"
        if _has_body(headers) and not headers.get("content-type", "").startswith(
            "application/json"
        ):
            return 415, "json_required"
        return None


def _has_body(headers: Headers) -> bool:
    length = headers.get("content-length")
    return "transfer-encoding" in headers or (length is not None and length != "0")
