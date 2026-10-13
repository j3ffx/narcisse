"""One canonical form per kind, so that the same trace found twice is one node."""

import pytest

from narcisse.domain import EntityKind
from narcisse.errors import AppError
from narcisse.normalize import normalize


@pytest.mark.parametrize(
    ("kind", "value", "display", "normalized"),
    [
        (EntityKind.NAME, "  Élodie   Exemple ", "Élodie Exemple", "elodie exemple"),
        (EntityKind.USERNAME, "@Jeanne.Exemple", "Jeanne.Exemple", "jeanne.exemple"),
        (EntityKind.EMAIL, " Jeanne@Example.ORG ", "Jeanne@Example.ORG", "jeanne@example.org"),
        (EntityKind.PHONE, "+33 6 39 98 00 00", "+33 6 39 98 00 00", "+33639980000"),
        (EntityKind.PHONE, "0033 (6) 39.98.00.00", "0033 (6) 39.98.00.00", "+33639980000"),
        (EntityKind.DOMAIN, "https://www.Example.org/contact", "example.org", "example.org"),
        (EntityKind.DOMAIN, "café.example", "xn--caf-dma.example", "xn--caf-dma.example"),
        (EntityKind.ORGANIZATION, "123 456 789", "123 456 789", "123456789"),
        (
            EntityKind.ORGANIZATION,
            "Exemple SARL (123 456 782)",
            "Exemple SARL (123 456 782)",
            "123456782",
        ),
        # One form for a number however it is written; French when no country code is given.
        (EntityKind.PHONE, "06 39 98 00 00", "06 39 98 00 00", "+33639980000"),
        (EntityKind.PHONE, "01-99-00-12-34", "01-99-00-12-34", "+33199001234"),
        (EntityKind.PHONE, "+1 650 253 0000", "+1 650 253 0000", "+16502530000"),
        (EntityKind.ORGANIZATION, "Société Exemple", "Société Exemple", "societe exemple"),
        (
            EntityKind.ACCOUNT,
            "http://WWW.Example.org:443/u/jeanne/#bio",
            "http://WWW.Example.org:443/u/jeanne/#bio",
            "https://example.org/u/jeanne",
        ),
        (
            EntityKind.URL,
            "https://example.org:8443/a?b=1",
            "https://example.org:8443/a?b=1",
            "https://example.org:8443/a?b=1",
        ),
    ],
)
def test_normal_forms(kind: EntityKind, value: str, display: str, normalized: str) -> None:
    assert normalize(kind, value) == (display, normalized)


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        (EntityKind.EMAIL, "jeanne.example.org"),
        (EntityKind.EMAIL, "jeanne@example"),
        (EntityKind.PHONE, "06 39 98"),
        (EntityKind.PHONE, "appelle-moi"),
        (EntityKind.DOMAIN, "pas un domaine"),
        (EntityKind.ACCOUNT, "ftp://example.org/jeanne"),
        (EntityKind.ACCOUNT, "example.org/jeanne"),
        (EntityKind.USERNAME, "jeanne exemple"),
        (EntityKind.NAME, "   "),
    ],
)
def test_invalid_values_are_refused_with_their_kind(kind: EntityKind, value: str) -> None:
    with pytest.raises(AppError) as error:
        normalize(kind, value)
    assert error.value.code == "invalid_value"
    assert error.value.params == {"kind": kind.value}
