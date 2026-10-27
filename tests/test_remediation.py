"""The action sheets: the knowledge base, the rules that pick what to do about a trace, the
letters Narcisse prepares, and the API that serves them."""

import json
from collections.abc import AsyncIterator
from datetime import date
from typing import ClassVar

import pytest

from narcisse.domain import EntityKind, EntityStatus, ProfileKind
from narcisse.engine.plugin import Finding, ModuleContext, ModuleMeta, SourceModule, Target
from narcisse.remediation import knowledge, letters
from narcisse.remediation.actions import TraceFacts, actions_for
from tests.conftest import Api, ApiFactory
from tests.fakes import meta

K = EntityKind


def facts(
    kind: EntityKind = K.ACCOUNT,
    normalized: str = "https://forum.example.org/u/jeanne",
    *,
    status: EntityStatus = EntityStatus.UNREVIEWED,
    modules: tuple[str, ...] = ("whatsmyname",),
    relations: tuple[str, ...] = (),
    urls: tuple[str, ...] = (),
    profile_kind: ProfileKind = ProfileKind.PERSONAL,
) -> TraceFacts:
    return TraceFacts(
        kind=kind,
        status=status,
        display=normalized,
        normalized=normalized,
        profile_kind=profile_kind,
        modules=frozenset(modules),
        relations=frozenset(relations),
        evidence_urls=urls,
    )


def codes(trace: TraceFacts) -> list[tuple[str, str | None]]:
    return [(a.code, a.service.name if a.service else None) for a in actions_for(trace)]


# Knowledge base


def test_a_site_is_known_by_its_host_or_a_parent_domain() -> None:
    github = knowledge.service_for_host("github.com")
    assert github is not None
    assert (github.name, github.source, github.category) == ("GitHub", "jdm", "account")
    assert knowledge.service_for_host("www.github.com") == github
    assert knowledge.service_for_host("gist.github.com") == github
    assert knowledge.service_for_host("github.example.org") is None
    assert knowledge.service_for_url("not an address") is None


def test_narcisse_own_sheets_win_over_justdeleteme() -> None:
    archive = knowledge.service_for_url("https://web.archive.org/web/2020/https://example.org")
    assert archive is not None
    assert (archive.source, archive.category, archive.email) == (
        "narcisse",
        "archive",
        "info@archive.org",
    )


def test_brokers_are_told_apart() -> None:
    broker = knowledge.is_broker("https://rocketreach.co/jeanne")
    assert broker is not None
    assert broker.name == "RocketReach"
    assert knowledge.is_broker("https://github.com/jeanne") is None


def test_every_official_link_is_https_and_dated() -> None:
    data = json.loads((knowledge.DATA / "guides.json").read_text(encoding="utf-8"))
    assert data["checked"]
    for key in data["links"]:
        assert knowledge.guide(key).url.startswith("https://")
    for service in data["services"]:
        assert service["url"].startswith("https://")
        assert service["domains"]


def test_the_justdeleteme_copy_says_where_it_comes_from() -> None:
    source = json.loads((knowledge.DATA / "jdm-source.json").read_text(encoding="utf-8"))
    assert source["licence"] == "MIT"
    assert "Permission is hereby granted" in source["notice"]
    assert len(source["commit"]) == 40


# Actions


def test_an_account_on_a_known_site_can_be_deleted_there() -> None:
    [delete, dereference] = actions_for(facts(normalized="https://github.com/jeanne"))
    assert delete.code == "delete_account"
    assert delete.service is not None
    assert delete.service.name == "GitHub"
    assert delete.url == delete.service.url
    assert delete.letter == "account_deletion"
    assert dereference.code == "dereference"
    assert {g.url for g in dereference.links} >= {
        "https://www.bing.com/webmaster/tools/eu-privacy-request",
        "https://report.qwant.com/removal/fr",
    }


def test_an_account_that_cannot_be_deleted_says_so_and_offers_a_letter() -> None:
    [cannot, _] = actions_for(facts(normalized="https://gravatar.com/jeanne"))
    assert (cannot.code, cannot.letter) == ("cannot_delete", "erasure")


def test_an_account_on_an_unknown_site() -> None:
    assert codes(facts()) == [("delete_account_unknown", None), ("dereference", None)]


@pytest.mark.parametrize(
    ("url", "code", "letter"),
    [
        ("https://rocketreach.co/p/jeanne", "broker_opt_out", "objection"),
        ("https://www.pappers.fr/entreprise/exemple", "directory_objection", "objection"),
        ("https://blog.example.org/2020/jeanne", "ask_site", "erasure"),
    ],
)
def test_a_page_about_the_user(url: str, code: str, letter: str) -> None:
    first, *rest = actions_for(facts(K.URL, url, modules=("searxng",)))
    assert (first.code, first.letter) == (code, letter)
    assert [a.code for a in rest] == ["dereference"]


def test_an_archived_page_goes_to_the_internet_archive_not_to_the_search_engines() -> None:
    page = facts(
        K.URL,
        "https://web.archive.org/web/2019/https://jeanne.example.org/",
        modules=("wayback",),
        relations=("archived_page",),
    )
    [archive] = actions_for(page)
    assert (archive.code, archive.email, archive.letter) == (
        "archive_removal",
        "info@archive.org",
        "archive",
    )


def test_what_is_archived_can_also_be_removed_from_the_archive() -> None:
    domain = facts(K.DOMAIN, "jeanne.example.org", modules=("wayback",), relations=("archived_at",))
    assert ("archive_removal", "Internet Archive (Wayback Machine)") in codes(domain)


def test_an_email_where_it_shows() -> None:
    email = facts(
        K.EMAIL,
        "jeanne@example.org",
        modules=("pgp", "gravatar", "github"),
        relations=("publishes_key", "commits_as"),
        urls=(
            "https://keys.openpgp.org/vks/v1/by-email/jeanne@example.org",
            "https://github.com/jeanne/project/commit/abc",
        ),
    )
    # The account a commit belongs to isn't the problem: the address in the commit is.
    assert codes(email) == [
        ("keyserver_hide", "keys.openpgp.org"),
        ("cannot_delete", "Gravatar"),
        ("commit_email", None),
    ]


def test_a_leak_cannot_be_removed_only_made_harmless() -> None:
    assert codes(facts(K.LEAK, "exemple 2019", modules=("xposedornot",))) == [("secure_leak", None)]


def test_a_phone_number() -> None:
    phone = facts(K.PHONE, "+33639980000", modules=("searxng",), urls=("https://www.pappers.fr/x",))
    assert codes(phone) == [("phone_opposition", None), ("directory_objection", "Pappers")]


def test_a_sensitive_subdomain_and_a_contact_the_registry_publishes() -> None:
    assert codes(facts(K.DOMAIN, "nas.example.org", modules=("certificates",))) == [
        ("restrict_subdomain", None)
    ]
    contact = facts(
        K.EMAIL, "jeanne@example.org", modules=("registration",), relations=("registrant",)
    )
    assert codes(contact) == [("whois_privacy", None)]


def test_what_the_register_of_companies_publishes() -> None:
    officer = facts(K.NAME, "Jeanne Exemple", modules=("companies",), relations=("officer",))
    assert codes(officer) == [("registry_diffusion", None)]
    office = facts(
        K.ADDRESS, "1 rue Exemple", modules=("companies",), relations=("registered_office",)
    )
    assert codes(office) == [("registry_diffusion", None)]


def test_a_professional_profile_keeps_what_it_expects_in_public() -> None:
    company = facts(
        K.ORGANIZATION, "123456782", modules=("companies",), relations=("registered_as",)
    )
    assert codes(company) == [("registry_diffusion", None)]
    pro = facts(
        K.ORGANIZATION,
        "123456782",
        modules=("companies",),
        relations=("registered_as",),
        profile_kind=ProfileKind.MIXED,
    )
    assert codes(pro) == [("keep_professional", None), ("registry_diffusion", None)]


def test_nothing_to_do_about_what_is_not_the_user_or_not_public() -> None:
    assert actions_for(facts(status=EntityStatus.FALSE_POSITIVE)) == []
    assert actions_for(facts(K.IDENTITY, "identity")) == []
    assert actions_for(facts(K.EMAIL, "jeanne@example.org", modules=("seed",))) == []


# Letters


def context(**overrides: object) -> letters.LetterContext:
    values: dict[str, object] = {
        "target": "https://forum.example.org/u/jeanne",
        "pages": ("https://forum.example.org/u/jeanne",),
        "service": "Forum Exemple",
        "name": "Jeanne Exemple",
        "email": "jeanne@example.org",
        "address": None,
        "today": date(2026, 10, 26),
    }
    values.update(overrides)
    return letters.LetterContext(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("template", [t for t in letters.TEMPLATES if t != "reminder"])
@pytest.mark.parametrize("lang", ["fr", "en"])
def test_every_letter_renders_in_both_languages(template: str, lang: letters.Lang) -> None:
    letter = letters.render(template, lang, context())
    assert letter.subject
    assert "{" not in letter.subject + letter.body
    assert "https://forum.example.org/u/jeanne" in letter.body


def test_a_letter_is_signed_with_the_profile_elements_and_blanks_for_the_rest() -> None:
    body = letters.render("erasure", "fr", context()).body
    assert "Forum Exemple" in body
    assert "article 17" in body
    assert "Jeanne Exemple\njeanne@example.org\n[à compléter : ton adresse postale" in body
    assert body.endswith("26 octobre 2026")
    blank = letters.render("erasure", "en", context(name=None, service=None)).body
    assert "[to fill in: your name]" in blank
    assert "[to fill in: the site's name]" in blank
    assert blank.endswith("26 October 2026")


def test_the_dereferencing_text_names_the_user() -> None:
    body = letters.render("dereference", "fr", context()).body
    assert "(Jeanne Exemple)" in body


# API


class Pages(SourceModule):
    """A page about the user on a business directory, and their company's domain."""

    meta: ClassVar[ModuleMeta] = meta("test.pages")

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        page = "https://www.pappers.fr/dirigeant/jeanne-exemple"
        yield Finding(kind=K.URL, value=page, relation="mentioned_on", url=page, confidence=0.8)
        yield Finding(kind=K.DOMAIN, value="exemple-sarl.example", relation="links_to", url=page)


async def test_the_action_sheet_of_a_trace(api: Api) -> None:
    profile = await api.profile(("name", "Jeanne Exemple"), ("email", "jeanne@example.org"))
    trace = await api.json(
        "POST", f"/profiles/{profile}/traces", {"url": "https://github.com/jeanne"}, status=201
    )

    sheet = await api.json("GET", f"/entities/{trace['id']}/remediation")

    assert sheet["complaint"]["url"] == "https://www.cnil.fr/fr/adresser-une-plainte"
    [delete, dereference] = sheet["actions"]
    assert delete["code"] == "delete_account"
    assert delete["service"]["name"] == "GitHub"
    assert delete["service"]["source"] == "jdm"
    assert delete["lang"] == "en"
    assert set(delete["letters"]) == {"fr", "en"}
    body = delete["letters"]["en"]["body"]
    assert "Jeanne Exemple\njeanne@example.org\n" in body
    assert "https://github.com/jeanne" in body
    assert dereference["lang"] == "fr"
    assert dereference["links"]


async def test_no_action_for_a_rejected_trace_or_the_identity(api: Api) -> None:
    profile = await api.profile(("name", "Jeanne Exemple"))
    trace = await api.json(
        "POST", f"/profiles/{profile}/traces", {"url": "https://blog.example.org/x"}, status=201
    )
    await api.json("PATCH", f"/entities/{trace['id']}", {"status": "false_positive"})
    assert (await api.json("GET", f"/entities/{trace['id']}/remediation"))["actions"] == []
    assert (await api.json("GET", "/entities/1/remediation"))["actions"] == []
    error = await api.json("GET", "/entities/999/remediation", status=404)
    assert error["code"] == "not_found"


async def test_a_professional_profile_rescores_its_traces(make_api: ApiFactory) -> None:
    api = await make_api({"test.pages": Pages()})
    profile = await api.profile(("name", "Jeanne Exemple"))
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    await api.wait_scan(scan["id"], lambda s: s["status"] == "done")
    graph = await api.json("GET", f"/profiles/{profile}/graph")
    [domain] = [n for n in graph["nodes"] if n["kind"] == "domain"]

    await api.json("PATCH", f"/profiles/{profile}", {"kind": "professional"})

    detail = await api.json("GET", f"/entities/{domain['id']}")
    assert detail["entity"]["risk"] < domain["risk"]
    assert "expected_professional" in [r["code"] for r in detail["reasons"]["risk"]]
    sheet = await api.json("GET", f"/entities/{domain['id']}/remediation")
    assert sheet["actions"][0]["code"] == "keep_professional"
    [page] = [n for n in graph["nodes"] if n["kind"] == "url"]
    page_sheet = await api.json("GET", f"/entities/{page['id']}/remediation")
    assert page_sheet["actions"][0]["code"] == "directory_objection"
    assert page_sheet["actions"][0]["lang"] == "fr"
