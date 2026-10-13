"""The archive and web search modules, against recorded-style answers (no network)."""

import httpx
import pytest
import respx

from narcisse.domain import EntityKind
from narcisse.engine.plugin import SourceUnavailable
from narcisse.modules.wayback import CDX, Wayback, notable
from tests.module_context import FakeContext, run, target

# Wayback Machine

SITE_ROWS = [
    ["timestamp", "original", "mimetype", "statuscode"],
    ["20140301120000", "http://jeanne-exemple.fr/", "text/html", "200"],
    ["20150611080000", "http://jeanne-exemple.fr/cv.pdf", "application/pdf", "200"],
    ["20160102030405", "http://jeanne-exemple.fr/contact/", "text/html", "200"],
    ["20160102030406", "http://jeanne-exemple.fr/contact/?lang=en", "text/html", "200"],
    ["20180909090909", "http://jeanne-exemple.fr/blog/a-legal-question", "text/html", "200"],
]


@respx.mock
async def test_the_archive_of_a_domain_and_its_pages_about_its_owner(
    http_client: httpx.AsyncClient,
) -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("matchType") == "domain":
            return httpx.Response(200, json=SITE_ROWS)
        return httpx.Response(200, json=[["timestamp"], ["20260901000000"]])

    route = respx.get(CDX).mock(side_effect=answer)
    module = Wayback()
    ctx = FakeContext(module, http_client)
    findings = await run(module, ctx, target(EntityKind.DOMAIN, "jeanne-exemple.fr"))

    overview = "https://web.archive.org/web/*/jeanne-exemple.fr*"
    assert [(f.relation, f.value, f.via) for f in findings] == [
        ("archived_at", overview, None),
        (
            "archived_page",
            "https://web.archive.org/web/20150611080000/http://jeanne-exemple.fr/cv.pdf",
            (EntityKind.URL, overview),
        ),
        (
            "archived_page",
            # One trace for a page, whatever its query string.
            "https://web.archive.org/web/20160102030406/http://jeanne-exemple.fr/contact/?lang=en",
            (EntityKind.URL, overview),
        ),
    ]
    assert findings[0].excerpt == (
        "5 pages de jeanne-exemple.fr archivées par la Wayback Machine, du 2014-03-01 au "
        "2026-09-01."
    )
    assert route.calls[0].request.url.params["collapse"] == "urlkey"
    assert ctx.notes == {"archived": 5, "notable": 2}


@respx.mock
async def test_a_profile_kept_by_the_archive(http_client: httpx.AsyncClient) -> None:
    respx.get(CDX).respond(
        200,
        json=[
            ["timestamp", "statuscode"],
            ["20190101000000", "200"],
            ["20210505000000", "200"],
            ["20230303000000", "404"],
        ],
    )
    module = Wayback()
    findings = await run(
        module,
        FakeContext(module, http_client),
        target(EntityKind.ACCOUNT, "https://forum.example.org/u/jeanne"),
    )
    assert [(f.relation, f.value) for f in findings] == [
        (
            "archived_at",
            "https://web.archive.org/web/20210505000000/https://forum.example.org/u/jeanne",
        )
    ]
    assert "2 mois différents, du 2019-01-01 au 2021-05-05" in (findings[0].excerpt or "")


@respx.mock
async def test_nothing_archived_and_a_site_excluded_from_the_archive(
    http_client: httpx.AsyncClient,
) -> None:
    module = Wayback()
    respx.get(CDX).respond(200, text="")
    ctx = FakeContext(module, http_client)
    assert await run(module, ctx, target(EntityKind.DOMAIN, "neuf-exemple.fr")) == []
    assert ctx.notes == {"archived": 0}

    respx.get(CDX).respond(
        403,
        text="AdministrativeAccessControlException: Blocked Site Error",
    )
    ctx = FakeContext(module, http_client)
    assert await run(module, ctx, target(EntityKind.DOMAIN, "exclu-exemple.fr")) == []
    assert ctx.notes == {"archive_excluded": 1}


@respx.mock
async def test_the_archive_offline(http_client: httpx.AsyncClient) -> None:
    respx.get(CDX).respond(200, html="<html><title>Internet Archive: Temporarily Offline</title>")
    module = Wayback()
    with pytest.raises(SourceUnavailable):
        await run(
            module, FakeContext(module, http_client), target(EntityKind.DOMAIN, "jeanne-exemple.fr")
        )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://jeanne-exemple.fr/cv/", True),
        ("http://jeanne-exemple.fr/a-propos.html", True),
        ("http://jeanne-exemple.fr/docs/rapport.PDF", True),
        ("http://jeanne-exemple.fr/blog/a-legal-question", False),
        ("http://jeanne-exemple.fr/contacts-utiles-du-quartier", False),
    ],
)
def test_pages_about_the_owner(url: str, expected: bool) -> None:
    assert notable(url, "text/html") is expected
