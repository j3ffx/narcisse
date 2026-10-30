"""The two languages Narcisse speaks, and which one to use.

The user chooses in the settings (`ui_lang`): French, English, or "auto". Auto follows the
browser for what the API returns (its Accept-Language), and the system for what Narcisse writes
on its own (notifications, the command line, live events). `NARCISSE_LANG` stands for the system
language in tests, which then don't depend on the machine they run on.
"""

import locale
import os
from collections.abc import Mapping
from typing import Literal, get_args

Lang = Literal["fr", "en"]
LANGS: tuple[Lang, ...] = get_args(Lang)
# Text in both languages, or the same text whatever the language.
Text = str | Mapping[str, str]


def _known(value: str | None) -> Lang | None:
    code = (value or "").strip().lower()[:2]
    return "fr" if code == "fr" else "en" if code == "en" else None


def system_lang() -> Lang:
    """The language of the machine (English when it is neither French nor English)."""
    chosen = _known(os.environ.get("NARCISSE_LANG"))
    if chosen:
        return chosen
    try:
        if os.name == "nt":
            import ctypes

            windll = getattr(ctypes, "windll", None)
            if windll is not None:
                code = locale.windows_locale.get(windll.kernel32.GetUserDefaultUILanguage())
                return _known(code) or "en"
        return _known(locale.getlocale()[0]) or "en"
    except (ValueError, OSError, AttributeError):
        return "en"


def accepted(header: str | None) -> Lang | None:
    """The first of our languages a browser's Accept-Language lists, by preference."""
    choices = []
    for index, part in enumerate((header or "").split(",")):
        tag, _, rest = part.strip().partition(";")
        quality = 1.0
        if rest.strip().startswith("q="):
            try:
                quality = float(rest.strip()[2:])
            except ValueError:
                quality = 0.0
        if (lang := _known(tag)) and quality > 0:
            choices.append((-quality, index, lang))
    return min(choices)[2] if choices else None


def resolve(preference: str | None, header: str | None = None) -> Lang:
    """The language to speak: the user's choice, else the browser's, else the system's."""
    return _known(preference) or accepted(header) or system_lang()


def pick(text: Text, lang: Lang) -> str:
    """The text in this language (French when it has no translation)."""
    if isinstance(text, str):
        return text
    return text.get(lang) or text.get("fr") or next(iter(text.values()), "")
