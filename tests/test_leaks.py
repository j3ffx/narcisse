"""The phone, leak and company modules, against recorded-style answers (no network)."""

import httpx
import pytest
import respx

from narcisse.domain import EntityKind
from narcisse.engine.plugin import InputRejected, RateLimited
from narcisse.modules.phone import Phone, describe
from narcisse.modules.xposedornot import API, XposedOrNot
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
