"""Links and addresses read in a profile's free text."""

from narcisse.domain import EntityKind
from narcisse.modules._text import emails, html_text, is_profile, links, text_findings


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
            where="dans la description Bluesky",
            confidence=0.6,
        )
    )
    assert [(f.kind, f.relation, f.value) for f in found] == [
        (EntityKind.ACCOUNT, "links_to", "https://github.com/jeanne-exemple"),
        (EntityKind.EMAIL, "shows_email", "jeanne@example.org"),
    ]
    assert found[0].excerpt == "Lien indiqué dans la description Bluesky."
