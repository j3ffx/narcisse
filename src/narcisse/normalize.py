"""One canonical form per kind of entity, so that the same trace found twice is one node."""

import re
import unicodedata
from contextlib import suppress
from urllib.parse import urlsplit, urlunsplit

import phonenumbers

from narcisse.domain import EntityKind
from narcisse.errors import AppError

_SPACES = re.compile(r"\s+")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]+$")
_PHONE_NOISE = re.compile(r"[\s.\-()/]")
_PHONE = re.compile(r"^\+?\d{8,15}$")
_DOMAIN = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")
_USERNAME = re.compile(r"^[^\s/]{1,100}$")
_SIREN_OR_SIRET = re.compile(r"^(\d{9}|\d{14})$")
# A company named with its SIREN (or SIRET) in brackets is the same company as that number.
_NAMED_SIREN = re.compile(r"\((\d{3} ?\d{3} ?\d{3}(?: ?\d{5})?)\)\s*$")
# Numbers written without a country code are French: the tool is French first.
DEFAULT_PHONE_REGION = "FR"


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


def phone_e164(digits: str) -> str:
    """One form for a number however it is written: « 01 99 00 12 34 » and « +33 1 99 00 12 34 »
    are +33199001234. A number without its country code is taken as French; one that can't be a
    number anywhere stays as written (digits only)."""
    try:
        number = phonenumbers.parse(digits, DEFAULT_PHONE_REGION)
    except phonenumbers.NumberParseException:
        return digits
    if not phonenumbers.is_possible_number(number):
        return digits
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


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
            normalized = phone_e164(digits)
        case EntityKind.DOMAIN:
            normalized = _domain(display)
            if not _DOMAIN.match(normalized):
                raise _invalid(kind)
            display = normalized
        case EntityKind.ORGANIZATION:
            digits = display.replace(" ", "")
            if _SIREN_OR_SIRET.match(digits):
                normalized = digits
            elif number := _NAMED_SIREN.search(display):
                normalized = number.group(1).replace(" ", "")  # « Exemple SARL (123 456 782) »
            else:
                normalized = fold(display)
        case EntityKind.ACCOUNT | EntityKind.URL:
            normalized = _url(display, kind)
        case EntityKind.LEAK | EntityKind.PHOTO:
            normalized = fold(display)
    return display, normalized
