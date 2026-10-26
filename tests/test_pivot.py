"""Scores in the app, leads, and scans that follow them (with modules the tests control)."""

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from sqlalchemy import update

from narcisse.domain import EntityKind
from narcisse.engine import pivot
from narcisse.engine.plugin import Finding, ModuleContext, ModuleMeta, SourceModule, Target
from narcisse.storage.models import Entity
from tests.conftest import Api, ApiFactory

SEED = "jeanne@example.org"


class Finds(SourceModule):
    """For each target, the e-mail addresses (and the confidence) the test tells it to find."""

    meta: ClassVar[ModuleMeta] = ModuleMeta(
        name="test.finds",
        title="Finds",
        description="Test module.",
        category="test",
        accepts=frozenset({EntityKind.EMAIL}),
        produces=frozenset({EntityKind.EMAIL}),
    )

    def __init__(self, leads: dict[str, list[tuple[str, float]]]) -> None:
        self.leads = leads
        self.seen: list[str] = []

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        self.seen.append(target.normalized)
        for value, confidence in self.leads.get(target.normalized, []):
            yield Finding(
                kind=EntityKind.EMAIL,
                value=value,
                relation="shows_email",
                confidence=confidence,
                url=f"https://source.example.org/{value}",
            )


async def scan(api: Api, profile: int, modules: list[str]) -> Any:
    started = await api.json("POST", f"/profiles/{profile}/scans", {"modules": modules}, 201)
    return await api.wait_scan(started["id"], lambda s: s["status"] == "done")


async def profile_with(api: Api, depth: int) -> int:
    profile = await api.profile(("email", SEED))
    await api.json("PATCH", f"/profiles/{profile}", {"settings": {"pivot_depth": depth}})
    return profile


async def entity_named(api: Api, profile: int, value: str) -> Any:
    graph = await api.json("GET", f"/profiles/{profile}/graph?false_positives=true")
    [node] = [n for n in graph["nodes"] if n["normalized"] == value]
    return node


# Scores in the app


async def test_found_traces_carry_their_scores_and_reasons(make_api: ApiFactory) -> None:
    finds = Finds({SEED: [("lead@example.org", 0.8)]})
    api = await make_api({"test.finds": finds})
    profile = await profile_with(api, 0)
    await scan(api, profile, ["test.finds"])

    lead = await entity_named(api, profile, "lead@example.org")
    assert (lead["confidence"], lead["risk"]) == (0.8, 0.27)  # 30 × (0.5 + 0.5 × 0.8)
    detail = await api.json("GET", f"/entities/{lead['id']}")
    assert [r["code"] for r in detail["reasons"]["confidence"]] == ["sources"]
    assert [r["code"] for r in detail["reasons"]["risk"]] == ["kind", "weighted"]

    seed = await entity_named(api, profile, SEED)
    assert seed["confidence"] == 1.0
    assert seed["risk"] == 0.0  # declared, never found in public


async def test_rejecting_a_trace_doubts_what_was_only_found_through_it(
    make_api: ApiFactory,
) -> None:
    finds = Finds(
        {SEED: [("lead@example.org", 0.8)], "lead@example.org": [("far@example.org", 0.8)]}
    )
    api = await make_api({"test.finds": finds})
    profile = await profile_with(api, 1)
    await scan(api, profile, ["test.finds"])
    far = await entity_named(api, profile, "far@example.org")
    assert far["confidence"] == 0.8

    lead = await entity_named(api, profile, "lead@example.org")
    await api.json("PATCH", f"/entities/{lead['id']}", {"status": "false_positive"})

    far = await api.json("GET", f"/entities/{far['id']}")
    assert far["entity"]["confidence"] == 0.24
    assert "via_rejected" in [r["code"] for r in far["reasons"]["confidence"]]


async def test_scores_are_computed_for_traces_stored_without_them(make_api: ApiFactory) -> None:
    finds = Finds({SEED: [("lead@example.org", 0.8)]})
    api = await make_api({"test.finds": finds})
    profile = await profile_with(api, 0)
    await scan(api, profile, ["test.finds"])
    async with api.app.state.services.db.write() as session:
        await session.execute(update(Entity).values(confidence=None, risk=None, score_reasons=None))
    await api.stop()

    api = await make_api({"test.finds": finds})  # a restart: scores come back
    lead = await entity_named(api, profile, "lead@example.org")
    assert lead["confidence"] == 0.8


# Leads


async def test_leads_are_the_sure_traces_that_arent_elements_yet(make_api: ApiFactory) -> None:
    finds = Finds({SEED: [("sure@example.org", 0.8), ("unsure@example.org", 0.4)]})
    api = await make_api({"test.finds": finds})
    profile = await profile_with(api, 0)
    await scan(api, profile, ["test.finds"])

    leads = await api.json("GET", f"/profiles/{profile}/leads")
    assert [lead["entity"]["normalized"] for lead in leads] == ["sure@example.org"]
    assert leads[0]["via"]["normalized"] == SEED
    assert leads[0]["relation"] == "shows_email"

    await api.json("PATCH", f"/entities/{leads[0]['entity']['id']}", {"pivot_dismissed": True})
    assert await api.json("GET", f"/profiles/{profile}/leads") == []


async def test_a_lead_added_as_an_element_is_no_longer_one(make_api: ApiFactory) -> None:
    finds = Finds({SEED: [("sure@example.org", 0.8)]})
    api = await make_api({"test.finds": finds})
    profile = await profile_with(api, 0)
    await scan(api, profile, ["test.finds"])
    await api.json(
        "POST", f"/profiles/{profile}/seeds", {"kind": "email", "value": "sure@example.org"}, 201
    )
    assert await api.json("GET", f"/profiles/{profile}/leads") == []


# Following leads


async def test_depth_zero_only_suggests(make_api: ApiFactory) -> None:
    finds = Finds({SEED: [("sure@example.org", 0.9)]})
    api = await make_api({"test.finds": finds})
    profile = await profile_with(api, 0)
    done = await scan(api, profile, ["test.finds"])
    assert {run["depth"] for run in done["runs"]} == {0}
    assert finds.seen == [SEED]


async def test_a_scan_follows_sure_leads_up_to_its_depth(make_api: ApiFactory) -> None:
    finds = Finds(
        {
            SEED: [("sure@example.org", 0.9), ("unsure@example.org", 0.5)],
            "sure@example.org": [("further@example.org", 0.9)],
            "further@example.org": [("too-far@example.org", 0.9)],
        }
    )
    api = await make_api({"test.finds": finds})
    profile = await profile_with(api, 2)
    done = await scan(api, profile, ["test.finds"])

    assert finds.seen == [SEED, "sure@example.org", "further@example.org"]
    assert sorted(run["depth"] for run in done["runs"]) == [0, 1, 2]
    assert done["notes"] == {"pivots": 2}


async def test_a_rejected_trace_is_never_followed(make_api: ApiFactory) -> None:
    finds = Finds({SEED: [("sure@example.org", 0.9)]})
    api = await make_api({"test.finds": finds})
    profile = await profile_with(api, 0)
    await scan(api, profile, ["test.finds"])
    sure = await entity_named(api, profile, "sure@example.org")
    await api.json("PATCH", f"/entities/{sure['id']}", {"status": "false_positive"})

    await api.json("PATCH", f"/profiles/{profile}", {"settings": {"pivot_depth": 2}})
    done = await scan(api, profile, ["test.finds"])
    assert {run["depth"] for run in done["runs"]} == {0}


async def test_a_scan_follows_no_more_leads_than_its_cap(make_api: ApiFactory) -> None:
    many = [(f"lead{i}@example.org", 0.9) for i in range(pivot.MAX_PIVOTS + 5)]
    finds = Finds({SEED: many})
    api = await make_api({"test.finds": finds})
    profile = await profile_with(api, 1)
    done = await scan(api, profile, ["test.finds"])

    assert done["notes"]["pivots"] == pivot.MAX_PIVOTS
    assert len(done["notes"]["capped"]) == 5
    assert len([run for run in done["runs"] if run["depth"] == 1]) == pivot.MAX_PIVOTS
