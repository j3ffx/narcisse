"""Has a password leaked? Pwned Passwords, by k-anonymity.

The page computes the password's SHA-1 itself; only the hash's first five characters reach
Narcisse, which asks Pwned Passwords for every hash that starts the same (padded with decoys) and
hands them back; the page compares. The password never leaves the page, and nothing is stored.
"""

import re

from fastapi import APIRouter

from narcisse.api.deps import ServicesDep
from narcisse.domain import EntityKind
from narcisse.engine.http import HttpClient
from narcisse.engine.plugin import ModuleError, ModuleMeta, RateLimit
from narcisse.errors import AppError
from narcisse.schemas import PasswordRangeOut

router = APIRouter(tags=["passwords"])

RANGE = "https://api.pwnedpasswords.com/range/"
HOST = "api.pwnedpasswords.com"
_PREFIX = re.compile(r"^[0-9A-Fa-f]{5}$")
# Not a source of the scans: a tool, with the same gate to the outside.
META = ModuleMeta(
    name="pwned-passwords",
    title="Pwned Passwords",
    description="Les empreintes de mots de passe apparus dans des fuites, en k-anonymat.",
    category="leaks",
    accepts=frozenset[EntityKind](),
    produces=frozenset[EntityKind](),
    hosts=(HOST,),
    rate_limit=RateLimit(requests=5, per_seconds=1),
)


def suffixes(text: str) -> list[tuple[str, int]]:
    """The hashes' suffixes and how often each appeared; the padding's decoys (0) left out."""
    found: list[tuple[str, int]] = []
    for line in text.splitlines():
        suffix, _, count = line.strip().partition(":")
        if len(suffix) == 35 and count.isdigit() and int(count) > 0:
            found.append((suffix.upper(), int(count)))
    return found


@router.get("/pwned-passwords/{prefix}")
async def password_range(prefix: str, s: ServicesDep) -> PasswordRangeOut:
    if not _PREFIX.match(prefix):
        raise AppError("invalid_request", status=422)
    engine = s.engine
    http = HttpClient(engine.http_client, engine.pacer, META, engine.clock)
    try:
        response = await http.get(f"{RANGE}{prefix.upper()}", headers={"Add-Padding": "true"})
    except ModuleError as exc:
        raise AppError(exc.code, status=502, params={"host": HOST}) from exc
    if response.status_code != 200:
        raise AppError(
            "source_refused", status=502, params={"host": HOST, "status": response.status_code}
        )
    return PasswordRangeOut(suffixes=suffixes(response.text))
