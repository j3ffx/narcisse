"""Opens a page in the user's own browser, for Narcisse's window.

Narcisse's window is the browser's `--app=` window: no tabs, no back button. A link that opened
in it would strand the user on the site. The window hands external links here instead, and they
open where the user's links always open: their default browser, in a tab of its own.
"""

import asyncio
import webbrowser
from urllib.parse import urlsplit

from fastapi import APIRouter, Response

from narcisse.api.deps import ServicesDep
from narcisse.errors import AppError
from narcisse.schemas import ExternalLinkIn

router = APIRouter(tags=["browser"])


@router.post("/open-external", status_code=204)
async def open_external(body: ExternalLinkIn, s: ServicesDep) -> Response:
    url = body.url.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise AppError("invalid_value", status=422)
    if f"{parts.scheme}://{parts.netloc}" in s.settings.own_origins:
        raise AppError("invalid_value", status=422)  # Narcisse's own pages stay in its window
    await asyncio.to_thread(webbrowser.open, url, 2)  # 2: a new tab
    return Response(status_code=204)
