"""The domain modules (registration, DNS, certificates, website), against recorded-style answers
(no network)."""

from typing import Any

import httpx
import pytest
import respx

from narcisse.domain import EntityKind
from narcisse.engine.plugin import InputRejected
from narcisse.modules.registration import HOSTS, RDAP, WHOIS, Registration
from tests.fakes import FakeWhois
from tests.module_context import FakeContext, run, target


def card(*props: list[Any]) -> list[Any]:
    return ["vcard", [["version", {}, "text", "4.0"], *props]]


def entity(roles: list[str], *props: list[Any], **more: Any) -> dict[str, Any]:
    return {"objectClassName": "entity", "roles": roles, "vcardArray": card(*props), **more}


def found(findings: list[Any]) -> list[tuple[EntityKind, str, str]]:
    return [(f.kind, f.relation, f.value) for f in findings]


# Registration (RDAP, WHOIS)


def test_the_registry_data_is_there() -> None:
    assert RDAP["fr"] == "https://rdap.nic.fr/"
    assert RDAP["com"].startswith("https://rdap.verisign.com/")
    assert "eu" not in RDAP
    assert WHOIS["eu"] == "whois.eu"
    assert "rdap.nic.fr" in HOSTS
    assert "whois.denic.de" in HOSTS


@respx.mock
async def test_a_registry_that_hides_the_holder_says_so(http_client: httpx.AsyncClient) -> None:
    respx.get("https://rdap.nic.fr/domain/jeanne-exemple.fr").respond(
        200,
        json={
            "events": [
                {"eventAction": "registration", "eventDate": "2019-03-02T10:00:00Z"},
                {"eventAction": "expiration", "eventDate": "2027-03-02T10:00:00Z"},
            ],
            "entities": [
                entity(["registrar"], ["fn", {}, "text", "Bureau Exemple SAS"]),
                entity(
                    ["registrant"],
                    ["fn", {}, "text", "REDACTED FOR PRIVACY"],
                    ["email", {}, "text", "redacted@example.net"],
                ),
            ],
        },
    )
    module = Registration()
    ctx = FakeContext(module, http_client)
    findings = await run(module, ctx, target(EntityKind.DOMAIN, "jeanne-exemple.fr"))

    assert found(findings) == [(EntityKind.ORGANIZATION, "registered_with", "Bureau Exemple SAS")]
    assert findings[0].excerpt == (
        "jeanne-exemple.fr est enregistré chez Bureau Exemple SAS le 2019-03-02, "
        "expire le 2027-03-02. Coordonnées du titulaire : masquées."
    )
    assert findings[0].attributes == {"created": "2019-03-02", "expires": "2027-03-02"}
    assert ctx.notes == {"published": 0, "redacted": 2}


@respx.mock
async def test_the_registrar_s_record_tells_what_the_registry_doesn_t(
    http_client: httpx.AsyncClient,
) -> None:
    registrar = "https://rdap.gandi.net/domain/jeanne-exemple.com"
    respx.get(f"{RDAP['com']}domain/jeanne-exemple.com").respond(
        200,
        json={
            "entities": [entity(["registrar"], ["fn", {}, "text", "Registrar Exemple Inc."])],
            "links": [
                {"rel": "related", "type": "application/rdap+json", "href": registrar},
                # Not a registrar's server: never followed.
                {
                    "rel": "related",
                    "type": "application/rdap+json",
                    "href": "https://elsewhere.example.net/domain/x",
                },
            ],
        },
    )
    respx.get(registrar).respond(
        200,
        json={
            "entities": [
                entity(
                    ["registrant"],
                    ["fn", {}, "text", "Jeanne Exemple"],
                    ["email", {}, "text", "jeanne@example.org"],
                    ["tel", {"type": "voice"}, "uri", "tel:+33.639980000"],
                    [
                        "adr",
                        {"label": "1 rue de l'Exemple\n75000 Paris\nFR"},
                        "text",
                        ["", "", "", "", "", "", ""],
                    ],
                ),
                entity(
                    ["technical"],
                    ["fn", {}, "text", "Hébergeur Exemple"],
                    ["email", {}, "text", "contact@privacy-protect.example.net"],
                ),
            ]
        },
    )
    module = Registration()
    findings = await run(
        module, FakeContext(module, http_client), target(EntityKind.DOMAIN, "jeanne-exemple.com")
    )

    assert found(findings) == [
        (EntityKind.ORGANIZATION, "registered_with", "Registrar Exemple Inc."),
        (EntityKind.NAME, "registrant", "Jeanne Exemple"),
        (EntityKind.EMAIL, "registrant", "jeanne@example.org"),
        (EntityKind.PHONE, "registrant", "+33.639980000"),
        (EntityKind.ADDRESS, "registrant", "1 rue de l'Exemple\n75000 Paris\nFR"),
        # The technical contact's name, but not the address of a privacy service.
        (EntityKind.NAME, "technical_contact", "Hébergeur Exemple"),
    ]
    assert findings[1].confidence == 0.6
    assert findings[1].excerpt == "Publié comme titulaire de jeanne-exemple.com par le registre."
    assert "Coordonnées du titulaire : publiées." in (findings[0].excerpt or "")


@respx.mock
async def test_a_subdomain_is_looked_up_through_its_parent(http_client: httpx.AsyncClient) -> None:
    respx.get("https://rdap.nic.fr/domain/blog.jeanne-exemple.fr").respond(404)
    respx.get("https://rdap.nic.fr/domain/jeanne-exemple.fr").respond(
        200,
        json={
            "entities": [
                entity(["registrar"], ["fn", {}, "text", "Bureau Exemple SAS"]),
                entity(["registrant"], ["org", {}, "text", "Hébergement Exemple"]),
            ]
        },
    )
    module = Registration()
    findings = await run(
        module,
        FakeContext(module, http_client),
        target(EntityKind.DOMAIN, "blog.jeanne-exemple.fr"),
    )
    assert found(findings)[1] == (EntityKind.ORGANIZATION, "registrant", "Hébergement Exemple")
    # The parent's holder is seldom the user (a hosting service, a blog platform…).
    assert findings[1].confidence == 0.2
    assert "domaine parent de blog.jeanne-exemple.fr" in (findings[1].excerpt or "")


@respx.mock
async def test_an_unregistered_domain(http_client: httpx.AsyncClient) -> None:
    respx.get(url__startswith="https://rdap.nic.fr/domain/").respond(404)
    module = Registration()
    ctx = FakeContext(module, http_client)
    assert await run(module, ctx, target(EntityKind.DOMAIN, "libre-exemple.fr")) == []
    assert ctx.notes == {"unregistered": 1}


async def test_a_top_level_domain_without_registry(http_client: httpx.AsyncClient) -> None:
    module = Registration()
    with pytest.raises(InputRejected) as rejected:
        await run(module, FakeContext(module, http_client), target(EntityKind.DOMAIN, "a.invalid"))
    assert rejected.value.code == "no_registry"


EURID = """\
% The WHOIS service offered by EURid and the access to the records
% in the EURid WHOIS database are provided for information purposes only.

Domain: jeanne-exemple.eu
Script: LATIN

Registrant:
        NOT DISCLOSED!
        Visit www.eurid.eu for webbased WHOIS.

Technical:
        Organisation: Hébergeur Exemple
        Language: fr
        Email: tech@hebergeur.example.net

Registrar:
        Name: Bureau Exemple SAS
        Website: https://registrar.example.net
"""

PUBLISHED = """\
Domain Name: jeanne-exemple.io
Registry Domain ID: 1234-EXEMPLE
Registrar: Registrar Exemple Inc.
Creation Date: 2021-05-06T07:08:09Z
Registry Expiry Date: 2027-05-06T07:08:09Z
Registrant Name: Jeanne Exemple
Registrant Organization:
Registrant Street: 1 rue de l'Exemple
Registrant Email: jeanne@example.org
Registrant Phone: +33.639980000
Admin Email: Please query the RDDS service of the Registrar of Record
Registrar Abuse Contact Email: abuse@registrar.example.net
"""


async def test_whois_for_a_registry_without_rdap(
    http_client: httpx.AsyncClient, whois: FakeWhois
) -> None:
    whois.answers[("whois.eu", "jeanne-exemple.eu")] = EURID
    module = Registration()
    ctx = FakeContext(module, http_client)
    findings = await run(module, ctx, target(EntityKind.DOMAIN, "jeanne-exemple.eu"))

    assert found(findings) == [
        (EntityKind.ORGANIZATION, "registered_with", "Bureau Exemple SAS"),
        (EntityKind.ORGANIZATION, "technical_contact", "Hébergeur Exemple"),
        (EntityKind.EMAIL, "technical_contact", "tech@hebergeur.example.net"),
    ]
    assert findings[0].url is None
    assert ctx.notes == {"published": 2, "redacted": 1}  # the holder: not disclosed


async def test_whois_in_the_common_format(http_client: httpx.AsyncClient, whois: FakeWhois) -> None:
    whois.answers[(WHOIS["io"], "jeanne-exemple.io")] = PUBLISHED
    module = Registration()
    ctx = FakeContext(module, http_client)
    findings = await run(module, ctx, target(EntityKind.DOMAIN, "jeanne-exemple.io"))

    assert found(findings) == [
        (EntityKind.ORGANIZATION, "registered_with", "Registrar Exemple Inc."),
        (EntityKind.NAME, "registrant", "Jeanne Exemple"),
        (EntityKind.EMAIL, "registrant", "jeanne@example.org"),
        (EntityKind.PHONE, "registrant", "+33.639980000"),
    ]
    assert "le 2021-05-06, expire le 2027-05-06" in (findings[0].excerpt or "")
    assert ctx.notes == {"published": 3, "redacted": 1}


async def test_whois_says_a_domain_is_free(
    http_client: httpx.AsyncClient, whois: FakeWhois
) -> None:
    whois.answers[("whois.dns.be", "libre-exemple.be")] = (
        "Domain: libre-exemple.be\nStatus: AVAILABLE\n"
    )
    module = Registration()
    ctx = FakeContext(module, http_client)
    assert await run(module, ctx, target(EntityKind.DOMAIN, "libre-exemple.be")) == []
    assert ctx.notes == {"unregistered": 1}
