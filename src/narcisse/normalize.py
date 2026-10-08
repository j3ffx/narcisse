"""One canonical form per kind of entity, so that the same trace found twice is one node."""

import re
import unicodedata
from contextlib import suppress
from urllib.parse import urlsplit, urlunsplit

from narcisse.domain import EntityKind
from narcisse.errors import AppError

_SPACES = re.compile(r"\s+")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]+$")
_PHONE_NOISE = re.compile(r"[\s.\-()/]")
_PHONE = re.compile(r"^\+?\d{8,15}$")
_DOMAIN = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")
_USERNAME = re.compile(r"^[^\s/]{1,100}$")
_SIREN_OR_SIRET = re.compile(r"^(\d{9}|\d{14})$")


def _invalid(kind: EntityKind) -> AppError:
    return AppError("invalid_value", status=422, params={"kind": kind.value})


def collapse(value: str) -> str:
    return _SPACES.sub(" ", value).strip()


def fold(value: str) -> str:
    """Case- and accent-insensitive form: « Élodie  Exemple » → « elodie exemple »."""
    decomposed = unicodedata.normalize("NFKD", collapse(value))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _domain(value: str) -> str:
    host = value.strip().lower()
    if "//" in host:
        host = urlsplit(host).hostname or ""
    host = host.split("/")[0].rstrip(".")
    host = host.removeprefix("www.")
    with suppress(UnicodeError):
        host = host.encode("idna").decode("ascii")
    return host


def _url(value: str, kind: EntityKind) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise _invalid(kind)
    host = _domain(parts.hostname)
    port = parts.port
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    path = parts.path.rstrip("/")
    # One form whatever the scheme: http and https pages of a profile are the same trace.
    return urlunsplit(("https", netloc, path, parts.query, ""))


def normalize(kind: EntityKind, value: str) -> tuple[str, str]:
    """Returns (display form, normalized form), or raises `invalid_value`."""
    display = collapse(value)
    if not display:
        raise _invalid(kind)
    match kind:
        case EntityKind.NAME | EntityKind.ADDRESS | EntityKind.IDENTITY:
            normalized = fold(display)
        case EntityKind.USERNAME:
            display = display.removeprefix("@")
            if not _USERNAME.match(display):
                raise _invalid(kind)
            normalized = display.casefold()
        case EntityKind.EMAIL:
            normalized = display.lower()
            if not _EMAIL.match(normalized):
                raise _invalid(kind)
        case EntityKind.PHONE:
            digits = _PHONE_NOISE.sub("", display)
            if digits.startswith("00"):
                digits = "+" + digits[2:]
            if not _PHONE.match(digits):
                raise _invalid(kind)
            normalized = digits
        case EntityKind.DOMAIN:
            normalized = _domain(display)
            if not _DOMAIN.match(normalized):
                raise _invalid(kind)
            display = normalized
        case EntityKind.ORGANIZATION:
            digits = display.replace(" ", "")
            normalized = digits if _SIREN_OR_SIRET.match(digits) else fold(display)
        case EntityKind.ACCOUNT | EntityKind.URL:
            normalized = _url(display, kind)
        case EntityKind.LEAK | EntityKind.PHOTO:
            normalized = fold(display)
    return display, normalized
