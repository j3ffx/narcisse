"""The phone, leak and company modules, against recorded-style answers (no network)."""

from typing import Any

import httpx
import pytest
import respx

from narcisse.domain import EntityKind
from narcisse.engine.plugin import InputRejected, RateLimited
from narcisse.modules.companies import BODACC, SEARCH, Companies, born, person_name
from narcisse.modules.phone import Phone, describe
from narcisse.modules.xposedornot import API, XposedOrNot
from narcisse.normalize import normalize
from tests.conftest import ApiFactory
from tests.module_context import FakeContext, run, target

# Phone


def test_a_number_described_without_asking_anyone() -> None:
    sentence, attributes = describe("+33612345678")
    assert sentence.startswith("Mobile, France. Opérateur d’origine : ")
    assert attributes["type"] == "mobile"
    assert attributes["international"] == "+33 6 12 34 56 78"
    assert Phone.meta.hosts == ()  # nothing leaves the machine

    # The numbers kept for fiction belong to no one.
    sentence, attributes = describe("+33639980000")
    assert attributes["valid"] == "no"
    assert "attribué à personne" in sentence

    with pytest.raises(InputRejected):
        describe("12")


async def test_a_finding_about_the_target_itself_adds_a_proof_and_no_edge(
    make_api: ApiFactory,
) -> None:
    api = await make_api({"phone": Phone()}, demo=False)
    profile = await api.profile(("phone", "06 12 34 56 78"))
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    await api.wait_scan(scan["id"], lambda s: s["status"] == "done")

    graph = await api.json("GET", f"/profiles/{profile}/graph")
    [phone] = [n for n in graph["nodes"] if n["kind"] == EntityKind.PHONE]
    assert phone["normalized"] == "+33612345678"
    assert phone["attributes"]["type"] == "mobile"
    assert phone["modules"] == ["seed", "phone"]
    # The identity declares it; nothing relates it to itself.
    assert [e["relation"] for e in graph["edges"]] == ["declares"]
    detail = await api.json("GET", f"/entities/{phone['id']}")
    [proof] = detail["evidence"]
    assert proof["module"] == "phone"
    assert proof["relation"] is None
    assert proof["excerpt"].startswith("Mobile, France.")


# XposedOrNot

BREACH = {
    "breach": "Exemple-Forum",
    "domain": "forum.example.org",
    "industry": "Information Technology",
    "password_risk": "easytocrack",
    "xposed_data": "Email addresses;Names;Passwords;Something New",
    "xposed_date": "2019",
    "xposed_records": 120000,
}
NOT_FOUND = {
    "BreachMetrics": None,
    "BreachesSummary": {"site": ""},
    "ExposedBreaches": None,
    "ExposedPastes": None,
    "PasteMetrics": None,
    "PastesSummary": {"cnt": 0, "domain": "", "tmpstmp": ""},
}


@respx.mock
async def test_the_breaches_an_address_appears_in(http_client: httpx.AsyncClient) -> None:
    route = respx.get(API).respond(
        200,
        json={
            "BreachesSummary": {"site": "Exemple-Forum;Exemple-Shop"},
            "ExposedBreaches": {
                "breaches_details": [
                    BREACH,
                    {"breach": "Exemple-Shop", "xposed_data": "Email addresses", "xposed_date": ""},
                ]
            },
        },
    )
    module = XposedOrNot()
    ctx = FakeContext(module, http_client)
    findings = await run(module, ctx, target(EntityKind.EMAIL, "jeanne@example.org"))

    assert route.calls.last.request.url.params["email"] == "jeanne@example.org"
    assert [(f.kind, f.relation, f.value) for f in findings] == [
        (EntityKind.LEAK, "exposed_in", "Exemple-Forum"),
        (EntityKind.LEAK, "exposed_in", "Exemple-Shop"),
    ]
    assert findings[0].excerpt == (
        "Fuite de forum.example.org en 2019 : adresses email, noms, mots de passe, Something New "
        "; mots de passe faciles à retrouver. Données : XposedOrNot."
    )
    assert findings[0].url == "https://xposedornot.com/breach/Exemple-Forum"
    assert findings[0].attributes["records"] == 120000
    assert findings[1].excerpt == "Fuite : adresses email. Données : XposedOrNot."
    assert ctx.notes == {"breaches": 2}


@respx.mock
async def test_an_address_in_no_breach(http_client: httpx.AsyncClient) -> None:
    respx.get(API).respond(200, json=NOT_FOUND)
    module = XposedOrNot()
    ctx = FakeContext(module, http_client)
    assert await run(module, ctx, target(EntityKind.EMAIL, "jeanne@example.org")) == []
    assert ctx.notes == {"breaches": 0}


@respx.mock
async def test_xposedornot_s_daily_cap(http_client: httpx.AsyncClient) -> None:
    respx.get(API).respond(429, headers={"Retry-After": "3600"})
    module = XposedOrNot()
    with pytest.raises(RateLimited) as limited:
        await run(
            module, FakeContext(module, http_client), target(EntityKind.EMAIL, "j@example.org")
        )
    assert limited.value.retry_after == 3600


# Companies


def officer(nom: str, prenoms: str, born: str = "1990-04", **more: str) -> dict[str, str]:
    return {
        "nom": nom,
        "prenoms": prenoms,
        "date_de_naissance": born,
        "qualite": "Gérant",
        "type_dirigeant": "personne physique",
        **more,
    }


def result(siren: str, name: str, *officers: dict[str, str], **more: Any) -> dict[str, Any]:
    return {
        "siren": siren,
        "nom_complet": name,
        "etat_administratif": "A",
        "date_creation": "2015-06-01",
        "siege": {"adresse": "1 RUE DE L'EXEMPLE 75000 PARIS"},
        "dirigeants": list(officers),
        **more,
    }


def page(*results: dict[str, Any]) -> dict[str, Any]:
    return {"results": list(results), "total_pages": 1, "total_results": len(results)}


@respx.mock
async def test_the_companies_a_person_runs_or_that_bear_their_name(
    http_client: httpx.AsyncClient,
) -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("est_entrepreneur_individuel") == "true":
            return httpx.Response(
                200,
                json=page(
                    result("123456782", "JEANNE EXEMPLE (EXEMPLE)"),
                    # Another person's sole trade, found by the search too.
                    result("732829320", "JEANNOT EXEMPLAIRE"),
                ),
            )
        return httpx.Response(
            200,
            json=page(
                result(
                    "552100554",
                    "EXEMPLE CONSEIL",
                    officer("EXEMPLE (EXEMPLE)", "JEANNE MARIE"),
                    officer("AUTRE", "PAUL"),
                ),
                # The name of a namesake's partner: not her.
                result("409834013", "AUTRE SOCIETE", officer("EXEMPLE", "LOUISE")),
            ),
        )

    route = respx.get(SEARCH).mock(side_effect=answer)
    module = Companies()
    ctx = FakeContext(module, http_client)
    findings = await run(module, ctx, target(EntityKind.NAME, "Jeanne Exemple"))

    first = route.calls[0].request.url.params
    assert (first["nom_personne"], first["prenoms_personne"]) == ("Exemple", "Jeanne")
    assert [(f.kind, f.relation, f.value) for f in findings] == [
        (EntityKind.ORGANIZATION, "company_officer", "EXEMPLE CONSEIL (552100554)"),
        (EntityKind.ADDRESS, "registered_office", "1 RUE DE L'EXEMPLE 75000 PARIS"),
        (EntityKind.ORGANIZATION, "sole_trader", "JEANNE EXEMPLE (EXEMPLE) (123456782)"),
        (EntityKind.ADDRESS, "registered_office", "1 RUE DE L'EXEMPLE 75000 PARIS"),
    ]
    assert findings[0].excerpt == (
        "Jeanne Marie Exemple, gérant, né·e en avril 1990, de EXEMPLE CONSEIL (en activité, "
        "créée le 2015-06-01). Siège : 1 RUE DE L'EXEMPLE 75000 PARIS."
    )
    assert findings[0].url == "https://annuaire-entreprises.data.gouv.fr/entreprise/552100554"
    assert findings[0].confidence == 0.4
    assert findings[1].via == (EntityKind.ORGANIZATION, "EXEMPLE CONSEIL (552100554)")
    assert ctx.notes == {"companies": 2}


@respx.mock
async def test_a_company_s_officers_office_and_notices(http_client: httpx.AsyncClient) -> None:
    respx.get(SEARCH).respond(
        200,
        json=page(result("552100554", "EXEMPLE CONSEIL", officer("EXEMPLE", "JEANNE"))),
    )
    bodacc = respx.get(BODACC).respond(
        200,
        json={
            "results": [
                {
                    "url_complete": "https://www.bodacc.fr/annonce/exemple-1",
                    "familleavis_lib": "Créations",
                    "dateparution": "2015-06-10",
                    "tribunal": "GREFFE DU TRIBUNAL DE COMMERCE DE PARIS",
                }
            ]
        },
    )
    module = Companies()
    ctx = FakeContext(module, http_client)
    findings = await run(module, ctx, target(EntityKind.ORGANIZATION, "552 100 554"))

    assert [(f.kind, f.relation, f.value) for f in findings] == [
        (EntityKind.ORGANIZATION, "registered_as", "EXEMPLE CONSEIL (552100554)"),
        (EntityKind.ADDRESS, "registered_office", "1 RUE DE L'EXEMPLE 75000 PARIS"),
        (EntityKind.NAME, "officer", "Jeanne Exemple"),
        (EntityKind.URL, "legal_notice", "https://www.bodacc.fr/annonce/exemple-1"),
    ]
    assert bodacc.calls.last.request.url.params["where"] == 'registre like "552100554"'
    assert findings[3].excerpt == (
        "Annonce au BODACC du 2015-06-10 : créations (EXEMPLE CONSEIL, greffe du tribunal de "
        "commerce de paris)."
    )
    assert ctx.notes == {"companies": 1, "officers": 1, "notices": 1}


def test_a_company_is_named_with_its_siren_one_trace_per_company() -> None:
    assert normalize(EntityKind.ORGANIZATION, "EXEMPLE CONSEIL (552100554)")[1] == "552100554"
    assert normalize(EntityKind.ORGANIZATION, "552 100 554")[1] == "552100554"
    assert born("1990-04") == "avril 1990"
    assert born(None) == ""
    assert person_name("EXEMPLE (DUPONT)", "JEANNE MARIE") == "Jeanne Marie Exemple"
    assert not Companies().accepts_target(EntityKind.NAME, "Jeanne")


# Pwned Passwords


async def test_a_password_is_checked_by_the_first_characters_of_its_hash(
    make_api: ApiFactory,
) -> None:
    calls: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            text=(
                "1E4C9B93F3F0682250B6CF8331B7EE68FD8:3861493\r\n"
                "00D4F6E8FA6EECAD2A3AA415EEC418D38EC:0\r\n"  # padding: a decoy
            ),
        )

    api = await make_api(None, demo=False, http_transport=httpx.MockTransport(answer))
    answer_ = await api.json("GET", "/pwned-passwords/5baa6")
    assert answer_ == {"suffixes": [["1E4C9B93F3F0682250B6CF8331B7EE68FD8", 3861493]]}
    assert str(calls[0].url) == "https://api.pwnedpasswords.com/range/5BAA6"
    assert calls[0].headers["Add-Padding"] == "true"
    # Only five hexadecimal characters ever go out.
    await api.json("GET", "/pwned-passwords/5baa61e4", status=422)
    await api.json("GET", "/pwned-passwords/motdepasse", status=422)
