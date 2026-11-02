"""Is there a newer version? Only if the user ticked the box in the settings.

Then, at most once a day, GitHub is asked for the latest release: it sees an address and Narcisse's
User-Agent, nothing about the user's data. Off by default, never in demo mode, and silent when it
fails: nothing here is worth an error message.
"""

import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Request

from narcisse import __version__
from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityKind
from narcisse.engine.http import HttpClient
from narcisse.engine.plugin import ModuleError, ModuleMeta, RateLimit
from narcisse.preferences import Preferences
from narcisse.schemas import UpdateOut

router = APIRouter(tags=["meta"])

HOST = "api.github.com"
LATEST = f"https://{HOST}/repos/j3ffx/narcisse/releases/latest"
# Where the page sends the user: fixed here, never taken from the answer.
RELEASES = "https://github.com/j3ffx/narcisse/releases/latest"
EVERY = timedelta(days=1)
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
# Not a source of the scans: a tool, with the same gate to the outside.
META = ModuleMeta(
    name="updates",
    title={"fr": "Nouvelles versions", "en": "New versions"},
    description={
        "fr": "La dernière version publiée de Narcisse.",
        "en": "The latest published version of Narcisse.",
    },
    category="meta",
    accepts=frozenset[EntityKind](),
    produces=frozenset[EntityKind](),
    hosts=(HOST,),
    rate_limit=RateLimit(requests=1, per_seconds=1),
)


def parse(version: object) -> tuple[int, ...] | None:
    match = _VERSION.match(version) if isinstance(version, str) else None
    return tuple(int(part) for part in match.groups()) if match else None


def newer(tag: object, current: str = __version__) -> str | None:
    """The version a release's tag names, if it is later than `current`."""
    found, mine = parse(tag), parse(current)
    if found is None or mine is None or found <= mine:
        return None
    return ".".join(str(part) for part in found)


async def _ask(s: ServicesDep) -> str | None:
    engine = s.engine
    http = HttpClient(engine.http_client, engine.pacer, META, engine.clock)
    try:
        response = await http.get(LATEST)
        if response.status_code != 200:
            return None
        body = response.json()
    except (ModuleError, ValueError):
        return None
    return newer(body.get("tag_name")) if isinstance(body, dict) else None


@router.get("/update")
async def get_update(request: Request, s: ServicesDep) -> UpdateOut:
    if s.settings.demo or not Preferences.load(s.settings.preferences_path).check_updates:
        return UpdateOut(latest=None, url=None)
    now = s.engine.clock.now()
    checked: tuple[datetime, str | None] | None = getattr(request.app.state, "update", None)
    if checked is None or now - checked[0] >= EVERY:
        checked = (now, await _ask(s))
        request.app.state.update = checked
    latest = checked[1]
    return UpdateOut(latest=latest, url=RELEASES if latest else None)
