"""The requests Narcisse prepares for the user to send: GDPR erasure (art. 17) and objection
(art. 21), account deletion, removal from the Internet Archive, and the text to paste into a
search engine's removal form.

Filled in with the profile's own elements (name, e-mail, postal address) when it has them, with
"[à compléter : …]" where it doesn't. The user reads, edits and sends them: Narcisse sends
nothing. The texts live in `data/letters/<lang>/<template>.txt`: the subject on the first line,
then a blank line, then the body.
"""

from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path
from typing import Literal

Lang = Literal["fr", "en"]
TEMPLATES = ("erasure", "objection", "account_deletion", "archive", "dereference")
LETTERS = Path(__file__).parent / "data" / "letters"

MONTHS = {
    "fr": (
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
}
BLANKS = {
    "fr": {
        "name": "[à compléter : ton nom]",
        "email": "[à compléter : ton adresse e-mail]",
        "address": "[à compléter : ton adresse postale, si tu veux une réponse par courrier]",
        "service": "[à compléter : le nom du site]",
    },
    "en": {
        "name": "[to fill in: your name]",
        "email": "[to fill in: your e-mail address]",
        "address": "[to fill in: your postal address, if you want a reply by post]",
        "service": "[to fill in: the site's name]",
    },
}


@dataclass(frozen=True, kw_only=True)
class LetterContext:
    target: str  # the trace, as shown
    pages: tuple[str, ...]  # the pages that show it
    service: str | None
    name: str | None
    email: str | None
    address: str | None
    today: date


@dataclass(frozen=True, kw_only=True)
class Letter:
    subject: str
    body: str


@cache
def _text(template: str, lang: Lang) -> tuple[str, str]:
    if template not in TEMPLATES:
        raise ValueError(template)
    text = (LETTERS / lang / f"{template}.txt").read_text(encoding="utf-8")
    subject, _, body = text.partition("\n\n")
    return subject.strip(), body.strip()


def _date(day: date, lang: Lang) -> str:
    month = MONTHS[lang][day.month - 1]
    return f"{day.day} {month} {day.year}"


def _list(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render(template: str, lang: Lang, ctx: LetterContext) -> Letter:
    blank = BLANKS[lang]
    name = ctx.name or blank["name"]
    email = ctx.email or blank["email"]
    address = ctx.address or blank["address"]
    service = ctx.service or blank["service"]
    concerned = _list(tuple(dict.fromkeys((ctx.target, *ctx.pages))))
    pages = _list(ctx.pages or (ctx.target,))
    signature = "\n".join((name, email, address, _date(ctx.today, lang)))
    subject, body = _text(template, lang)
    fields = {
        "name": name,
        "service": service,
        "target": ctx.target,
        "concerned": concerned,
        "pages": pages,
        "signature": signature,
    }
    return Letter(subject=subject.format(**fields), body=body.format(**fields))
