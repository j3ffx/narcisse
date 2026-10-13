"""The domain modules (registration, DNS, certificates, website), against recorded-style answers
(no network)."""

from typing import Any

import httpx
import pytest
import respx

from narcisse.domain import EntityKind
from narcisse.engine.plugin import InputRejected, RateLimited
from narcisse.modules.certificates import Certificates
from narcisse.modules.dns_records import Dns, DomainMissing, service_of, soa_email, spf_includes
from narcisse.modules.registration import HOSTS, RDAP, WHOIS, Registration
from narcisse.modules.website import Website, siren_valid
from narcisse.preferences import Preferences
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
async def test_a_subdomain_of_a_public_suffix_climbs_past_a_400(
    http_client: httpx.AsyncClient,
) -> None:
    # Google's .dev RDAP answers 400 for nuagerie.pages.dev (not a registrable name); the run must
    # not fail, it climbs to pages.dev. Reported by the user on their real data (2026-10-13).
    base = RDAP["dev"]
    respx.get(f"{base}domain/nuagerie.pages.dev").respond(400)
    respx.get(f"{base}domain/pages.dev").respond(
        200, json={"entities": [entity(["registrar"], ["fn", {}, "text", "Cloudflare"])]}
    )
    module = Registration()
    findings = await run(
        module, FakeContext(module, http_client), target(EntityKind.DOMAIN, "nuagerie.pages.dev")
    )
    assert found(findings) == [(EntityKind.ORGANIZATION, "registered_with", "Cloudflare")]
    assert "domaine parent de nuagerie.pages.dev" in (findings[0].excerpt or "")


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


# DNS


class FakeDns(Dns):
    """The DNS module, asking a table instead of the resolver."""

    def __init__(
        self, records: dict[tuple[str, str], list[str]], missing: frozenset[str] = frozenset()
    ) -> None:
        self.records = records
        self.missing = missing
        self.asked: list[tuple[str, str]] = []

    async def query(self, name: str, rdtype: str) -> list[str]:
        self.asked.append((name, rdtype))
        if name in self.missing:
            raise DomainMissing(name)
        return self.records.get((name, rdtype), [])


async def test_dns_names_the_services_a_domain_relies_on(http_client: httpx.AsyncClient) -> None:
    domain = "jeanne-exemple.fr"
    module = FakeDns(
        {
            (domain, "MX"): ["aspmx.l.google.com.", "alt1.aspmx.l.google.com."],
            (domain, "NS"): ["dns200.anycast.me.", "ns200.anycast.me."],
            (domain, "TXT"): [
                "v=spf1 include:_spf.google.com include:servers.mcsv.net ~all",
                "google-site-verification=abc",
                "apple-domain-verification=def",
                "a record nobody knows",
            ],
            (f"_atproto.{domain}", "TXT"): ["did=did:plc:exemple"],
            (domain, "A"): ["185.199.108.153", "192.0.2.10"],
            ("10.2.0.192.in-addr.arpa.", "PTR"): ["ip-192-0-2-10.eu-west.compute.amazonaws.com."],
            (f"_dmarc.{domain}", "TXT"): [
                "v=DMARC1; p=none; rua=mailto:jeanne@example.org,mailto:report@dmarc.example.net; "
                "ruf=mailto:dmarc@jeanne-exemple.fr"
            ],
            (domain, "SOA"): [r"jeanne\.exemple.gmail.com."],
        }
    )
    ctx = FakeContext(module, http_client)
    findings = await run(module, ctx, target(EntityKind.DOMAIN, domain))

    assert found(findings) == [
        (EntityKind.ORGANIZATION, "uses_service", "Google Workspace"),
        (EntityKind.ORGANIZATION, "uses_service", "OVHcloud"),
        (EntityKind.ORGANIZATION, "uses_service", "Mailchimp"),
        (EntityKind.ORGANIZATION, "uses_service", "Google (Search Console)"),
        (EntityKind.ORGANIZATION, "uses_service", "Apple"),
        (EntityKind.ORGANIZATION, "uses_service", "Bluesky"),
        (EntityKind.ORGANIZATION, "uses_service", "GitHub Pages"),
        (EntityKind.ORGANIZATION, "uses_service", "Amazon Web Services"),
        # Not the DMARC service's address: it isn't the user's.
        (EntityKind.EMAIL, "dmarc_reports", "dmarc@jeanne-exemple.fr"),
        (EntityKind.EMAIL, "dns_contact", "jeanne.exemple@gmail.com"),
    ]
    assert findings[0].excerpt == (
        "Les emails de jeanne-exemple.fr sont reçus par Google Workspace (MX aspmx.l.google.com)."
    )
    assert findings[4].excerpt == (
        "jeanne-exemple.fr a été vérifié auprès d’Apple (apple-domain-verification=def)."
    )
    assert findings[0].attributes == {"service": "mail"}
    # Addresses of the user's domain and of webmails only.
    assert "jeanne@example.org" not in [f.value for f in findings]
    assert ctx.notes == {"records": 8, "services": 8}


async def test_dns_of_a_domain_that_doesn_t_exist(http_client: httpx.AsyncClient) -> None:
    module = FakeDns({}, missing=frozenset({"absent-exemple.fr"}))
    with pytest.raises(InputRejected) as rejected:
        await run(
            module, FakeContext(module, http_client), target(EntityKind.DOMAIN, "absent-exemple.fr")
        )
    assert rejected.value.code == "domain_not_found"


@pytest.mark.parametrize(
    ("rname", "email"),
    [
        ("hostmaster.example.org.", "hostmaster@example.org"),
        (r"jeanne\.exemple.example.org.", "jeanne.exemple@example.org"),
        ("localhost", None),
    ],
)
def test_the_address_in_an_soa_record(rname: str, email: str | None) -> None:
    assert soa_email(rname) == email


def test_services_match_on_suffixes_and_parts() -> None:
    assert service_of("mx", "aspmx.l.google.com.") == "Google Workspace"
    assert service_of("mx", "notgoogle.com") is None
    assert service_of("ns", "ns-421.awsdns-52.com.") == "Amazon Route 53"
    assert spf_includes("v=spf1 +include:a.example.net ~all redirect=b.example.net") == [
        "a.example.net",
        "b.example.net",
    ]


# Certificates


@respx.mock
async def test_subdomains_and_addresses_from_certificate_logs(
    http_client: httpx.AsyncClient,
) -> None:
    route = respx.get("https://crt.sh/").respond(
        200,
        json=[
            {
                "name_value": "nas.jeanne-exemple.fr\n*.jeanne-exemple.fr",
                "not_before": "2021-01-02T00:00:00",
                "not_after": "2021-04-02T00:00:00",
            },
            {
                "name_value": "nas.jeanne-exemple.fr\ncloud.jeanne-exemple.fr",
                "not_before": "2024-05-06T00:00:00",
                "not_after": "2024-08-04T00:00:00",
            },
            {
                "name_value": "jeanne@jeanne-exemple.fr\nautre-exemple.fr",
                "not_before": "2023-01-01T00:00:00",
                "not_after": "2024-01-01T00:00:00",
            },
        ],
    )
    module = Certificates()
    ctx = FakeContext(module, http_client)
    findings = await run(module, ctx, target(EntityKind.DOMAIN, "jeanne-exemple.fr"))

    assert route.calls.last.request.url.params["q"] == "%.jeanne-exemple.fr"
    assert found(findings) == [
        (EntityKind.DOMAIN, "subdomain", "nas.jeanne-exemple.fr"),
        (EntityKind.DOMAIN, "subdomain", "cloud.jeanne-exemple.fr"),
        (EntityKind.EMAIL, "certificate_email", "jeanne@jeanne-exemple.fr"),
    ]
    assert findings[0].excerpt == (
        "Nom vu dans 2 certificats, du 2021-01-02 au 2024-08-04 (crt.sh)."
    )
    assert findings[0].url == "https://crt.sh/?q=nas.jeanne-exemple.fr"
    assert ctx.notes == {"certificates": 3, "subdomains": 2}


@respx.mock
async def test_cert_spotter_stands_in_when_crt_sh_is_down(http_client: httpx.AsyncClient) -> None:
    respx.get("https://crt.sh/").respond(502)
    spotter = respx.get("https://api.certspotter.com/v1/issuances").mock(
        side_effect=[
            httpx.Response(
                200,
                json=[
                    {
                        "id": "41",
                        "dns_names": ["vpn.jeanne-exemple.fr"],
                        "not_before": "2026-09-01T00:00:00Z",
                        "not_after": "2026-11-30T00:00:00Z",
                    }
                ],
            ),
            httpx.Response(200, json=[]),
        ]
    )
    module = Certificates()
    findings = await run(
        module, FakeContext(module, http_client), target(EntityKind.DOMAIN, "jeanne-exemple.fr")
    )

    assert found(findings) == [(EntityKind.DOMAIN, "subdomain", "vpn.jeanne-exemple.fr")]
    assert findings[0].url is None
    assert findings[0].excerpt == (
        "Nom vu dans 1 certificat encore valide, du 2026-09-01 au 2026-11-30 (Cert Spotter)."
    )
    assert spotter.calls[0].request.url.params["include_subdomains"] == "true"
    assert spotter.calls[1].request.url.params["after"] == "41"


@respx.mock
async def test_certificates_when_both_logs_are_down(http_client: httpx.AsyncClient) -> None:
    respx.get("https://crt.sh/").respond(502)
    respx.get("https://api.certspotter.com/v1/issuances").respond(
        429, headers={"Retry-After": "600"}
    )
    module = Certificates()
    with pytest.raises(RateLimited) as limited:
        await run(
            module, FakeContext(module, http_client), target(EntityKind.DOMAIN, "jeanne-exemple.fr")
        )
    assert limited.value.retry_after == 600


# Website

SITE = "https://jeanne-exemple.fr"
HOME = """<!doctype html><html><head><title>Jeanne Exemple</title>
<script>var tel = "06 39 98 00 99";</script></head>
<body><h1>Jeanne Exemple, photographe</h1>
<p>Écrivez-moi : <a href="mailto:jeanne@jeanne-exemple.fr">jeanne@jeanne-exemple.fr</a></p>
<nav><a href="/mentions-legales">Mentions légales</a> <a href="/contact/">Me contacter</a>
<a href="/blog/">Blog</a> <a href="https://elsewhere.example.net/about">À propos d'eux</a></nav>
<footer><a href="https://social.example.net/@jeanne">Mastodon</a>
<a href="https://social.example.net/@jeanne">Encore</a></footer>
</body></html>"""
LEGAL = """<html><body><h2>Éditeur</h2>
<p>Le directeur de la publication du site est Madame Jeanne Exemple.</p>
<p>Siège : 1 rue de l'Exemple
75000 Paris, téléphone 06 39 98 00 12, SIREN 123 456 782.</p>
<p>Déclarée en préfecture sous le n° 0784012789.</p>
<p>L'hébergement du site est assuré par la société Hébergeur Exemple, RCS Exemple 732 829 320,
2 avenue des Serveurs, 59100 Roubaix, téléphone 01 99 00 12 34.</p>
</body></html>"""


def site(robots: str = "User-agent: *\nDisallow: /contact/\n") -> None:
    respx.get(f"{SITE}/robots.txt").respond(200, text=robots)
    respx.get(f"{SITE}/").respond(200, html=HOME)
    respx.get(f"{SITE}/mentions-legales").respond(200, html=LEGAL)


@respx.mock
async def test_the_site_s_legal_notice_tells_who_runs_it(http_client: httpx.AsyncClient) -> None:
    site()
    contact = respx.get(f"{SITE}/contact/").respond(200, html="<p>contact</p>")
    module = Website()
    what = target(EntityKind.DOMAIN, "jeanne-exemple.fr")
    ctx = FakeContext(module, http_client, target=what)
    findings = await run(module, ctx, what)

    page = (EntityKind.URL, f"{SITE}/mentions-legales")
    assert [(f.kind, f.relation, f.value, f.via) for f in findings] == [
        (EntityKind.EMAIL, "shows_email", "jeanne@jeanne-exemple.fr", None),
        (EntityKind.ACCOUNT, "links_to", "https://social.example.net/@jeanne", None),
        (EntityKind.URL, "has_page", f"{SITE}/mentions-legales", None),
        (EntityKind.PHONE, "shows_phone", "06 39 98 00 12", page),
        (EntityKind.PHONE, "shows_phone", "01 99 00 12 34", page),
        (EntityKind.ORGANIZATION, "shows_siren", "123456782", page),
        (EntityKind.ORGANIZATION, "shows_siren", "732829320", page),
        (EntityKind.NAME, "publisher", "Jeanne Exemple", page),
        (EntityKind.ADDRESS, "shows_address", "1 rue de l'Exemple, 75000 Paris", page),
        (EntityKind.ADDRESS, "shows_address", "2 avenue des Serveurs, 59100 Roubaix", page),
    ]
    confidence = {f.value: f.confidence for f in findings}
    # What the notice says of the host: not the user's.
    assert confidence["01 99 00 12 34"] == 0.3
    assert confidence["732829320"] == 0.3
    assert confidence["2 avenue des Serveurs, 59100 Roubaix"] == 0.3
    assert confidence["Jeanne Exemple"] == 0.7
    assert "Madame Jeanne Exemple" in (findings[7].excerpt or "")
    # robots.txt keeps the contact page out; the script's number and the registration number
    # aren't phones.
    assert not contact.called
    assert "06 39 98 00 99" not in confidence
    assert "0784012789" not in confidence
    assert ctx.notes == {"pages": 2, "robots": 1}


@respx.mock
async def test_the_site_reached_through_its_www(http_client: httpx.AsyncClient) -> None:
    respx.get(f"{SITE}/robots.txt").respond(404)
    respx.get(f"{SITE}/").respond(301, headers={"Location": "https://www.jeanne-exemple.fr/"})
    respx.get("https://www.jeanne-exemple.fr/robots.txt").respond(404)
    respx.get("https://www.jeanne-exemple.fr/").respond(
        200, html="<p>Contact : jeanne@jeanne-exemple.fr</p>"
    )
    module = Website()
    what = target(EntityKind.DOMAIN, "jeanne-exemple.fr")
    findings = await run(module, FakeContext(module, http_client, target=what), what)
    assert found(findings) == [(EntityKind.EMAIL, "shows_email", "jeanne@jeanne-exemple.fr")]
    assert findings[0].url == "https://www.jeanne-exemple.fr/"


@respx.mock
async def test_a_site_that_redirects_elsewhere_is_a_trace(http_client: httpx.AsyncClient) -> None:
    respx.get(f"{SITE}/robots.txt").respond(404)
    respx.get(f"{SITE}/").respond(302, headers={"Location": "https://social.example.net/@jeanne"})
    elsewhere = respx.get("https://social.example.net/@jeanne")
    module = Website()
    what = target(EntityKind.DOMAIN, "jeanne-exemple.fr")
    findings = await run(module, FakeContext(module, http_client, target=what), what)
    assert found(findings) == [
        (EntityKind.ACCOUNT, "redirects_to", "https://social.example.net/@jeanne")
    ]
    assert not elsewhere.called


async def test_the_site_module_may_reach_the_domain_only(http_client: httpx.AsyncClient) -> None:
    module = Website()
    what = target(EntityKind.DOMAIN, "jeanne-exemple.fr")
    assert module.allowed_hosts(Preferences(), what) == (
        "jeanne-exemple.fr",
        "www.jeanne-exemple.fr",
    )
    assert module.allowed_hosts(Preferences()) == ()
    assert module.meta.other_hosts


@pytest.mark.parametrize(
    ("digits", "valid"), [("123456782", True), ("123456789", False), ("732829320", True)]
)
def test_a_siren_carries_a_luhn_check(digits: str, valid: bool) -> None:
    assert siren_valid(digits) is valid
