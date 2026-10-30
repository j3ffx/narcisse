"""The archive and web search modules, against recorded-style answers (no network)."""

import re
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from narcisse import cli, searxng
from narcisse.config import Settings
from narcisse.domain import EntityKind
from narcisse.engine.plugin import SourceUnavailable, Target
from narcisse.modules.searxng import SearXNG, mentions
from narcisse.modules.wayback import CDX, Wayback, notable
from narcisse.preferences import Preferences
from tests.conftest import ApiFactory
from tests.fakes import said
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
    assert said(findings[0]) == (
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
    assert "2 mois différents, du 2019-01-01 au 2021-05-05" in said(findings[0])


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


# SearXNG

INSTANCE = "http://127.0.0.1:8888"
WITH_INSTANCE = Preferences(searxng_url=INSTANCE)


def results(*items: dict[str, Any]) -> dict[str, Any]:
    return {"query": "q", "results": list(items)}


@respx.mock
async def test_searxng_keeps_the_pages_that_name_you(http_client: httpx.AsyncClient) -> None:
    route = respx.get(f"{INSTANCE}/search").mock(
        side_effect=[
            httpx.Response(
                200,
                json=results(
                    {
                        "url": "https://club.example.org/membres/jeanne",
                        "title": "Jeanne Exemple, trésorière",
                        "content": "Le bureau du club : Jeanne Exemple…",
                        "engines": ["duckduckgo", "brave"],
                    },
                    # A near match the engine also gave: left out.
                    {"url": "https://example.net/jean", "title": "Jean Exemplaire", "content": ""},
                    {
                        "url": "https://social.example.net/@jeanne",
                        "title": "Élodie (JEANNE EXEMPLE)",
                    },
                ),
            ),
            httpx.Response(200, json=results()),
        ]
    )
    module = SearXNG()
    ctx = FakeContext(module, http_client, preferences=WITH_INSTANCE)
    findings = await run(module, ctx, target(EntityKind.NAME, "Jeanne Exemple"))

    assert route.calls[0].request.url.params["q"] == '"Jeanne Exemple"'
    assert route.calls[0].request.url.params["format"] == "json"
    assert [(f.kind, f.relation, f.value) for f in findings] == [
        (EntityKind.URL, "mentioned_on", "https://club.example.org/membres/jeanne"),
        (EntityKind.ACCOUNT, "mentioned_on", "https://social.example.net/@jeanne"),
    ]
    assert findings[0].confidence == 0.3
    assert said(findings[0]) == "Jeanne Exemple, trésorière — Le bureau du club : Jeanne Exemple…"
    assert findings[0].attributes == {"engines": ["duckduckgo", "brave"]}
    assert ctx.notes == {"results": 3, "found": 2}


@respx.mock
async def test_a_domain_is_searched_outside_of_itself(http_client: httpx.AsyncClient) -> None:
    route = respx.get(f"{INSTANCE}/search").respond(
        200,
        json=results(
            {"url": "https://jeanne-exemple.fr/blog", "title": "jeanne-exemple.fr"},
            {"url": "https://annuaire.example.org/sites", "content": "voir jeanne-exemple.fr"},
        ),
    )
    module = SearXNG()
    findings = await run(
        module,
        FakeContext(module, http_client, preferences=WITH_INSTANCE),
        target(EntityKind.DOMAIN, "jeanne-exemple.fr"),
    )
    assert route.calls[0].request.url.params["q"] == '"jeanne-exemple.fr" -site:jeanne-exemple.fr'
    assert [f.value for f in findings] == ["https://annuaire.example.org/sites"]


def test_a_phone_is_found_however_it_is_written() -> None:
    phone = Target(
        entity_id=1, kind=EntityKind.PHONE, value="06 39 98 00 00", normalized="0639980000"
    )
    assert mentions(phone, {"content": "Appelez le +33 6 39 98 00 00"})
    assert not mentions(phone, {"content": "Appelez le 06 39 98 00 01"})


@respx.mock
async def test_an_instance_without_json(http_client: httpx.AsyncClient) -> None:
    respx.get(f"{INSTANCE}/search").respond(403)
    module = SearXNG()
    with pytest.raises(SourceUnavailable) as refused:
        await run(
            module,
            FakeContext(module, http_client, preferences=WITH_INSTANCE),
            target(EntityKind.NAME, "Jeanne Exemple"),
        )
    assert refused.value.code == "searxng_json_off"


@respx.mock
async def test_an_instance_that_does_not_answer_says_so(http_client: httpx.AsyncClient) -> None:
    respx.get(f"{INSTANCE}/search").mock(side_effect=httpx.ConnectError("refused"))
    module = SearXNG()
    with pytest.raises(SourceUnavailable) as down:
        await run(
            module,
            FakeContext(module, http_client, preferences=WITH_INSTANCE),
            target(EntityKind.NAME, "Jeanne Exemple"),
        )
    assert (down.value.code, down.value.params) == ("searxng_down", {"host": "127.0.0.1"})


def test_searxng_needs_an_instance_and_reaches_it_only() -> None:
    module = SearXNG()
    assert module.unavailable(Preferences()) == "searxng_not_set"
    assert module.unavailable(WITH_INSTANCE) is None
    assert module.allowed_hosts(WITH_INSTANCE) == ("127.0.0.1",)
    assert module.allowed_hosts(Preferences()) == ()


async def test_a_source_that_can_t_run_is_left_out_of_scans(
    make_api: ApiFactory, tmp_path: Path
) -> None:
    api = await make_api({"searxng": SearXNG()}, demo=False)
    listed = await api.json("GET", "/modules")
    assert listed[0]["unavailable"] == "searxng_not_set"
    profile = await api.json("POST", "/profiles", {"name": "Jeanne Exemple"}, status=201)
    await api.json(
        "POST",
        f"/profiles/{profile['id']}/seeds",
        {"kind": "name", "value": "Jeanne Exemple"},
        status=201,
    )
    refused = await api.client.post(f"/api/profiles/{profile['id']}/scans", json={})
    assert refused.status_code == 409
    assert refused.json()["code"] == "nothing_to_scan"

    shown = await api.json("PATCH", "/preferences", {"searxng_url": " http://127.0.0.1:8888/ "})
    assert shown["searxng_url"] == "http://127.0.0.1:8888"
    assert (await api.json("GET", "/modules"))[0]["unavailable"] is None
    await api.json("PATCH", "/preferences", {"searxng_url": "pas une adresse"}, status=422)
    assert (await api.json("PATCH", "/preferences", {"searxng_url": ""}))["searxng_url"] is None


def test_narcisse_writes_a_searxng_of_one_s_own(monkeypatch: pytest.MonkeyPatch) -> None:
    folder = searxng.directory()
    assert CliRunner().invoke(cli.app, ["searxng", "--no-start"]).exit_code == 0
    compose = (folder / "docker-compose.yml").read_text(encoding="utf-8")
    settings = (folder / "config" / "settings.yml").read_text(encoding="utf-8")
    assert '"127.0.0.1:8888:8080"' in compose  # this machine only
    assert "- json" in settings
    assert "limiter: false" in settings
    secret = re.search(r'secret_key: "([0-9a-f]{64})"', settings)
    assert secret is not None
    # Written again: the secret stays.
    CliRunner().invoke(cli.app, ["searxng", "--no-start"])
    assert (folder / "config" / "settings.yml").read_text(encoding="utf-8") == settings


def test_narcisse_starts_its_searxng_and_sets_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("NARCISSE_DATA_DIR", str(tmp_path / "data"))
    started: list[Path] = []

    def start(folder: Path) -> tuple[bool, str]:
        started.append(folder)
        return True, ""

    monkeypatch.setattr(searxng, "docker", lambda: "docker")
    monkeypatch.setattr(searxng, "start", start)
    monkeypatch.setattr(searxng, "ready", lambda address: True)
    result = CliRunner().invoke(cli.app, ["searxng"])
    assert result.exit_code == 0, result.output
    assert started == [searxng.directory()]
    saved = Preferences.load(Settings.from_env(demo=False).preferences_path)
    assert saved.searxng_url == "http://127.0.0.1:8888"

    monkeypatch.setattr(searxng, "start", lambda folder: (False, "daemon not running"))
    failed = CliRunner().invoke(cli.app, ["searxng"])
    assert failed.exit_code == 1
    assert "Docker Desktop" in failed.output
