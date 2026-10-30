"""Links and addresses read in a profile's free text, and the profile each finding was read on."""

from collections.abc import AsyncIterator

from narcisse import notes
from narcisse.domain import EntityKind
from narcisse.engine.plugin import Finding
from narcisse.modules._text import (
    emails,
    html_text,
    is_profile,
    links,
    read_on_profiles,
    text_findings,
)
from narcisse.notes import note
from tests.fakes import said


def test_links_in_plain_text_lose_the_punctuation_that_follows_them() -> None:
    text = "Mon site : https://jeanne.example.org. Et (https://example.com/a?b=1), voilà."
    assert links(text) == ["https://jeanne.example.org", "https://example.com/a?b=1"]


def test_links_in_html_skip_mentions_and_hashtags() -> None:
    note = (
        '<p>Je suis <a href="https://jeanne.example.org/" rel="me">jeanne.example.org</a>, '
        'amie de <span class="h-card"><a href="https://social.example/@paul" '
        'class="u-url mention">@paul</a></span> '
        '<a href="https://social.example/tags/osint" class="mention hashtag">#osint</a></p>'
    )
    assert links(note, html=True) == ["https://jeanne.example.org/"]


def test_addresses_in_text_and_mailto_links() -> None:
    assert emails("Écrivez-moi : jeanne@example.org.") == ["jeanne@example.org"]
    assert emails('<a href="mailto:contact@example.net">écrire</a>', html=True) == [
        "contact@example.net"
    ]
    # A Fediverse handle is not an address.
    assert emails("Aussi sur @jeanne@social.example.org") == []


def test_html_text_keeps_one_line_per_paragraph() -> None:
    assert html_text("<p>Bonjour&nbsp;!</p><p>Lyon<br>France</p>") == "Bonjour\xa0!\nLyon\nFrance"


def test_profile_links_are_told_from_other_pages() -> None:
    profiles = [
        "https://github.com/jeanne-exemple",
        "https://www.linkedin.com/in/jeanne-exemple/",
        "https://social.example.org/@jeanne",
        "https://news.ycombinator.com/user?id=jeanne",
        "https://bsky.app/profile/jeanne.bsky.social",
    ]
    pages = [
        "https://github.com/jeanne-exemple/notes",
        "https://github.com/explore",
        "https://jeanne.example.org/",
        "https://example.com/@",
    ]
    assert all(is_profile(url) for url in profiles)
    assert not any(is_profile(url) for url in pages)


def test_text_findings_tell_where_each_trace_was_read() -> None:
    found = list(
        text_findings(
            "https://github.com/jeanne-exemple et jeanne@example.org",
            url="https://bsky.app/profile/jeanne.bsky.social",
            where=note("in_bluesky_description", handle="jeanne.bsky.social"),
            confidence=0.6,
        )
    )
    assert [(f.kind, f.relation, f.value) for f in found] == [
        (EntityKind.ACCOUNT, "links_to", "https://github.com/jeanne-exemple"),
        (EntityKind.EMAIL, "shows_email", "jeanne@example.org"),
    ]
    assert said(found[0]) == (
        "Lien indiqué dans la description du compte Bluesky « jeanne.bsky.social »."
    )
    assert notes.render(found[1].note, "en") == (
        "Address given in the description of the Bluesky account “jeanne.bsky.social”."
    )


async def test_what_follows_a_profile_is_read_on_it() -> None:
    async def module() -> AsyncIterator[Finding]:
        yield Finding(kind=EntityKind.NAME, value="Avant", relation="shows_name")
        yield Finding(
            kind=EntityKind.ACCOUNT, value="https://a.example.org/j", relation="has_account"
        )
        yield Finding(kind=EntityKind.URL, value="https://jeanne.example.org", relation="links_to")
        yield Finding(
            kind=EntityKind.EMAIL,
            value="jeanne@example.org",
            relation="shows_email",
            via=(EntityKind.URL, "https://jeanne.example.org"),
        )
        yield Finding(
            kind=EntityKind.ACCOUNT, value="https://b.example.org/j", relation="has_account"
        )
        yield Finding(kind=EntityKind.NAME, value="Jeanne", relation="shows_name")

    found = [f.via async for f in read_on_profiles(module())]
    assert found == [
        None,  # nothing read yet: the target
        None,  # a profile relates to the target
        (EntityKind.ACCOUNT, "https://a.example.org/j"),
        (EntityKind.URL, "https://jeanne.example.org"),  # said by the module: kept
        None,
        (EntityKind.ACCOUNT, "https://b.example.org/j"),
    ]
