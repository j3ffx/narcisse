"""What a profile's free text gives away: the links and e-mail addresses in a bio, an "about",
a description. Shared by the modules that read profiles (not a module itself: the name starts
with an underscore).
"""

import re
from collections.abc import Iterator
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit

from narcisse.domain import EntityKind
from narcisse.engine.plugin import Finding

_URL = re.compile(r"https?://[^\s<>\"'()\[\]{}]+", re.IGNORECASE)
# Not a Fediverse handle (`@name@instance`).
_EMAIL = re.compile(r"(?<![\w.+@-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# A link ends before the punctuation that follows it in a sentence.
_TRAILING = ".,;:!?…»"

# Sites whose `https://site/<name>` page is a profile.
_ONE_SEGMENT = frozenset(
    {
        "github.com",
        "gitlab.com",
        "codeberg.org",
        "framagit.org",
        "x.com",
        "twitter.com",
        "instagram.com",
        "facebook.com",
        "keybase.io",
        "t.me",
        "twitch.tv",
        "linktr.ee",
        "about.me",
        "patreon.com",
        "ko-fi.com",
        "pinterest.com",
        "soundcloud.com",
        "vimeo.com",
        "dribbble.com",
        "behance.net",
    }
)
# Sites whose profile pages sit under a prefix: `https://site/<prefix>/<name>`.
_PREFIXED = {
    "linkedin.com": ("in",),
    "reddit.com": ("user", "u"),
    "bsky.app": ("profile",),
    "stackoverflow.com": ("users",),
    "youtube.com": ("c", "channel", "user"),
}
# First path segments that are pages of the site, not someone's name.
_RESERVED = frozenset({"about", "explore", "help", "home", "login", "search", "settings", "share"})


class _Html(HTMLParser):
    """The text of a fragment of HTML, and the targets of its links (but mentions and hashtags,
    which point at other people and topics)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("br", "p", "div", "li"):
            self.text.append("\n")
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "a" and values.get("href") and not {"mention", "hashtag"} & set(classes):
            self.hrefs.append(values["href"] or "")

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def html_text(html: str) -> str:
    """The text of a fragment of HTML, one line per paragraph."""
    parser = _Html()
    parser.feed(html)
    parser.close()
    return re.sub(r"\n\s*\n+", "\n", "".join(parser.text)).strip()


def _clean(url: str) -> str:
    return url.rstrip(_TRAILING)


def links(text: str, *, html: bool = False) -> list[str]:
    """The web addresses in a text (or in a fragment of HTML: its links and its text), once each,
    in order."""
    found: list[str] = []
    if html:
        parser = _Html()
        parser.feed(text)
        parser.close()
        found += [unescape(h) for h in parser.hrefs if h.lower().startswith(("http:", "https:"))]
        text = "".join(parser.text)
    found += [_clean(m.group()) for m in _URL.finditer(text)]
    return list(dict.fromkeys(found))


def emails(text: str, *, html: bool = False) -> list[str]:
    """The e-mail addresses in a text (or in a fragment of HTML, `mailto:` links included)."""
    if html:
        mailto = re.findall(r"mailto:([^\"'?>\s]+)", text, re.IGNORECASE)
        text = html_text(text) + "\n" + "\n".join(unescape(m) for m in mailto)
    return list(dict.fromkeys(m.group().rstrip(".") for m in _EMAIL.finditer(text)))


def is_profile(url: str) -> bool:
    """Whether a link points at someone's profile on a known site (an account), rather than at
    any page."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) == 1 and segments[0].startswith("@") and len(segments[0]) > 1:
        return True  # Mastodon and the like, YouTube, Medium, TikTok, Threads…
    if host == "news.ycombinator.com":
        return segments == ["user"] and "id=" in parts.query
    if host in _ONE_SEGMENT:
        return len(segments) == 1 and segments[0].lower() not in _RESERVED
    prefixes = _PREFIXED.get(host)
    return bool(prefixes) and len(segments) >= 2 and segments[0] in (prefixes or ())


def text_findings(
    text: str, *, html: bool = False, url: str, where: str, confidence: float
) -> Iterator[Finding]:
    """A finding for each link and address in a profile's text. `where` completes « Lien indiqué
    … » (e.g. « dans la bio Bluesky de « jeanne » »); `url` is the profile, the proof."""
    for link in links(text, html=html):
        if urlsplit(link).hostname is None:
            continue
        yield Finding(
            kind=EntityKind.ACCOUNT if is_profile(link) else EntityKind.URL,
            value=link,
            relation="links_to",
            confidence=confidence,
            url=url,
            excerpt=f"Lien indiqué {where}.",
        )
    for email in emails(text, html=html):
        yield Finding(
            kind=EntityKind.EMAIL,
            value=email,
            relation="shows_email",
            confidence=confidence,
            url=url,
            excerpt=f"Adresse indiquée {where}.",
        )
