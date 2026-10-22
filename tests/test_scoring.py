"""The confidence and risk rules, one by one, on traces built by hand."""

from typing import Any

import pytest

from narcisse.domain import EntityKind, EntityStatus
from narcisse.engine.scoring import (
    Link,
    Neighbour,
    Trace,
    confidence,
    risk,
    risk_level,
    score,
)

K = EntityKind
S = EntityStatus


def trace(
    kind: EntityKind = K.ACCOUNT,
    *,
    status: EntityStatus = S.UNREVIEWED,
    declared: bool = False,
    normalized: str = "https://forum.example.org/u/jeanne",
    module_confidence: float | None = 0.6,
    modules: tuple[str, ...] = ("whatsmyname",),
    attributes: dict[str, Any] | None = None,
    links: tuple[Link, ...] = (),
) -> Trace:
    return Trace(
        kind=kind,
        status=status,
        declared=declared,
        normalized=normalized,
        module_confidence=module_confidence,
        modules=frozenset(modules),
        attributes=attributes or {},
        links=links,
    )


def neighbour(
    kind: EntityKind = K.USERNAME,
    *,
    status: EntityStatus = S.UNREVIEWED,
    declared: bool = False,
    display: str = "jeanne",
) -> Neighbour:
    return Neighbour(kind=kind, status=status, declared=declared, display=display)


def link(other: Neighbour, *, relation: str = "has_account", incoming: bool = True) -> Link:
    return Link(relation=relation, module="whatsmyname", other=other, incoming=incoming)


def codes(reasons: tuple[Any, ...]) -> list[str]:
    return [r.code for r in reasons]


# Confidence


def test_the_sources_confidence_is_the_starting_point() -> None:
    points, reasons = confidence(trace(module_confidence=0.6))
    assert points == 60
    assert codes(reasons) == ["sources"]


def test_a_source_without_confidence_counts_as_one_in_two() -> None:
    points, reasons = confidence(trace(module_confidence=None))
    assert points == 50
    assert codes(reasons) == ["no_source_confidence"]


@pytest.mark.parametrize(
    ("status", "declared", "kind", "expected", "code"),
    [
        (S.UNREVIEWED, True, K.EMAIL, 100, "declared"),
        (S.CONFIRMED, False, K.ACCOUNT, 100, "confirmed"),
        (S.FALSE_POSITIVE, False, K.ACCOUNT, 0, "rejected"),
        (S.CONFIRMED, False, K.IDENTITY, 100, "identity"),
    ],
)
def test_the_users_word_settles_it(
    status: EntityStatus, declared: bool, kind: EntityKind, expected: int, code: str
) -> None:
    points, reasons = confidence(trace(kind, status=status, declared=declared))
    assert points == expected
    assert codes(reasons) == [code]


@pytest.mark.parametrize(("modules", "bonus"), [(2, 10), (3, 15), (5, 15)])
def test_independent_sources_add_up(modules: int, bonus: int) -> None:
    names = tuple(f"source{i}" for i in range(modules))
    points, reasons = confidence(trace(module_confidence=0.5, modules=names))
    assert points == 50 + bonus
    assert reasons[1].code == "several_sources"
    assert reasons[1].params["count"] == modules


def test_a_trace_the_user_added_is_not_an_independent_source() -> None:
    points, _ = confidence(trace(module_confidence=0.5, modules=("whatsmyname", "manual")))
    assert points == 50


def test_tying_two_of_the_users_traces_together_is_corroboration() -> None:
    username = neighbour(K.USERNAME, declared=True, display="jeanne")
    email = neighbour(K.EMAIL, declared=True, display="jeanne@example.org")
    points, reasons = confidence(
        trace(
            module_confidence=0.5,
            links=(link(username), link(email, relation="shows_email", incoming=False)),
        )
    )
    assert points == 65
    assert "corroborated" in codes(reasons)


def test_one_declared_element_alone_adds_nothing() -> None:
    points, _ = confidence(trace(module_confidence=0.5, links=(link(neighbour(declared=True)),)))
    assert points == 50


def test_found_from_a_confirmed_trace() -> None:
    confirmed = neighbour(K.ACCOUNT, status=S.CONFIRMED, display="https://code.example.com/j")
    points, reasons = confidence(trace(K.EMAIL, module_confidence=0.5, links=(link(confirmed),)))
    assert points == 60
    assert reasons[-1].code == "via_confirmed"
    assert reasons[-1].params["trace"] == "https://code.example.com/j"


def test_only_reached_through_rejected_traces() -> None:
    rejected = neighbour(K.ACCOUNT, status=S.FALSE_POSITIVE)
    points, reasons = confidence(trace(K.EMAIL, module_confidence=0.8, links=(link(rejected),)))
    assert points == 24  # 80 × 0.3
    assert reasons[-1].code == "via_rejected"
    assert reasons[-1].factor == 0.3


def test_one_good_path_is_enough_to_keep_it() -> None:
    rejected = neighbour(K.ACCOUNT, status=S.FALSE_POSITIVE)
    fine = neighbour(K.ACCOUNT, display="https://photos.example.net/j")
    points, reasons = confidence(
        trace(K.EMAIL, module_confidence=0.8, links=(link(rejected), link(fine)))
    )
    assert points == 80
    assert "via_rejected" not in codes(reasons)


def test_an_unreviewed_trace_never_reaches_certainty() -> None:
    username = neighbour(K.USERNAME, declared=True, display="jeanne")
    email = neighbour(K.EMAIL, declared=True, display="jeanne@example.org")
    points, reasons = confidence(
        trace(
            module_confidence=0.95,
            modules=("a", "b", "c"),
            links=(link(username), link(email)),
        )
    )
    assert points == 95
    assert reasons[-1].code == "unreviewed_cap"


# Risk


@pytest.mark.parametrize(
    ("kind", "base"),
    [(K.ADDRESS, 70), (K.PHONE, 60), (K.LEAK, 50), (K.EMAIL, 30), (K.USERNAME, 10)],
)
def test_each_kind_has_its_base(kind: EntityKind, base: int) -> None:
    points, reasons = risk(trace(kind), 100)
    assert points == base
    assert reasons[0].code == "kind"


def test_uncertainty_weighs_the_risk_down() -> None:
    points, reasons = risk(trace(K.ADDRESS), 40)
    assert points == 49  # 70 × (0.5 + 0.5 × 0.4)
    assert reasons[-1].code == "weighted"
    assert reasons[-1].factor == 0.7


def test_nothing_public_no_exposure() -> None:
    points, reasons = risk(trace(K.PHONE, declared=True, modules=()), 100)
    assert points == 0
    assert codes(reasons) == ["not_public"]


def test_a_declared_element_found_in_public_is_exposed() -> None:
    points, _ = risk(trace(K.PHONE, declared=True, modules=("website",)), 100)
    assert points == 60


def test_a_rejected_trace_exposes_nothing() -> None:
    points, reasons = risk(trace(K.ADDRESS, status=S.FALSE_POSITIVE), 0)
    assert points == 0
    assert codes(reasons) == ["rejected"]


def test_a_leak_with_readable_passwords_and_papers() -> None:
    leak = trace(
        K.LEAK,
        modules=("xposedornot",),
        attributes={
            "data": ["adresses email", "mots de passe", "numéros de passeport"],
            "password_risk": "plaintext",
        },
    )
    points, reasons = risk(leak, 100)
    assert points == 100  # 50 + 30 + 30, capped
    assert {"leaked_passwords", "leaked_identity"} <= set(codes(reasons))


def test_hashed_passwords_are_not_counted_as_readable() -> None:
    leak = trace(
        K.LEAK,
        modules=("xposedornot",),
        attributes={"data": ["mots de passe"], "password_risk": "hardtocrack"},
    )
    points, reasons = risk(leak, 100)
    assert points == 50
    assert "leaked_passwords" not in codes(reasons)


@pytest.mark.parametrize(
    ("kind", "normalized", "modules", "attributes", "code", "points"),
    [
        (K.ORGANIZATION, "123456789", ("companies",), {"birth": "1980-05"}, "birth_published", 45),
        (K.ACCOUNT, "https://adult.example/j", ("whatsmyname",), {"adult": True}, "adult_site", 60),
        (K.ACCOUNT, "https://rocketreach.co/", ("rocketreach",), {}, "data_broker", 50),
        (K.ACCOUNT, "https://www.strava.com/", ("strava",), {}, "movements", 40),
        (K.DOMAIN, "nas.jeanne-exemple.fr", ("certificates",), {}, "sensitive_subdomain", 40),
    ],
)
def test_what_a_trace_reveals_adds_to_its_risk(
    kind: EntityKind,
    normalized: str,
    modules: tuple[str, ...],
    attributes: dict[str, Any],
    code: str,
    points: int,
) -> None:
    got, reasons = risk(
        trace(kind, normalized=normalized, modules=modules, attributes=attributes), 100
    )
    assert got == points
    assert code in codes(reasons)


def test_a_plain_subdomain_or_a_registrable_domain_is_not_sensitive() -> None:
    for name in ("blog.jeanne-exemple.fr", "nas.fr", "vpn"):
        _, reasons = risk(trace(K.DOMAIN, normalized=name, modules=("dns",)), 100)
        assert "sensitive_subdomain" not in codes(reasons)


def test_contact_details_the_domain_registry_publishes() -> None:
    domain = neighbour(K.DOMAIN, declared=True, display="jeanne-exemple.fr")
    points, reasons = risk(
        trace(K.EMAIL, modules=("registration",), links=(link(domain, relation="registrant"),)),
        100,
    )
    assert points == 50
    assert "registry_contact" in codes(reasons)


def test_an_archived_copy() -> None:
    site = neighbour(K.DOMAIN, declared=True, display="jeanne-exemple.fr")
    _, reasons = risk(
        trace(K.URL, modules=("wayback",), links=(link(site, relation="archived_page"),)), 100
    )
    assert "archived" in codes(reasons)


def test_the_identity_itself_is_neither_exposed_nor_doubted() -> None:
    scores = score(trace(K.IDENTITY, status=S.CONFIRMED, modules=()))
    assert (scores.confidence, scores.risk) == (1.0, 0.0)


# Together


def test_score_gives_both_on_a_zero_to_one_scale_with_their_reasons() -> None:
    scores = score(trace(K.ADDRESS, module_confidence=0.5, modules=("companies",)))
    assert scores.confidence == 0.5
    assert scores.risk == 0.52  # 70 × 0.75 = 52.5, rounded to even
    assert scores.reasons_json() == {
        "confidence": [{"code": "sources", "points": 50}],
        "risk": [
            {"code": "kind", "points": 70, "params": {"kind": "address"}},
            {"code": "weighted", "factor": 0.75},
        ],
    }


@pytest.mark.parametrize(
    ("value", "level"),
    [
        (0.0, "low"),
        (0.24, "low"),
        (0.25, "medium"),
        (0.5, "high"),
        (0.74, "high"),
        (0.75, "critical"),
        (1.0, "critical"),
    ],
)
def test_risk_levels(value: float, level: str) -> None:
    assert risk_level(value) == level
