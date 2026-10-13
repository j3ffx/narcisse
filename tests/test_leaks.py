"""The phone, leak and company modules, against recorded-style answers (no network)."""

import pytest

from narcisse.domain import EntityKind
from narcisse.engine.plugin import InputRejected
from narcisse.modules.phone import Phone, describe
from tests.conftest import ApiFactory

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
