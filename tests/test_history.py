"""What changed between two scans, and the profile's exports."""

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from narcisse.domain import EntityKind
from narcisse.engine.plugin import Finding, ModuleContext, ModuleMeta, SourceModule, Target
from tests.conftest import Api, ApiFactory
from tests.fakes import meta


class Pages(SourceModule):
    """Finds the pages it is told to, each with the content it is told to."""

    meta: ClassVar[ModuleMeta] = meta("test.pages")

    def __init__(self) -> None:
        self.pages: dict[str, str] = {}

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(0, 1)
        for url, content in self.pages.items():
            yield Finding(
                kind=EntityKind.URL, value=url, relation="mentioned_on", url=url, content=content
            )


class Quiet(SourceModule):
    meta: ClassVar[ModuleMeta] = meta("test.quiet")

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(1, 1)
        return
        yield  # pragma: no cover


A = "https://a.example.org/jeanne"
B = "https://b.example.org/jeanne"
C = "https://c.example.org/jeanne"


async def scanned(api: Api, profile: int, modules: list[str] | None = None) -> dict[str, Any]:
    body = {"modules": modules} if modules else {}
    scan = await api.json("POST", f"/profiles/{profile}/scans", body, status=201)
    done: dict[str, Any] = await api.wait_scan(scan["id"], lambda s: s["status"] == "done")
    return done


def displays(items: list[dict[str, Any]]) -> list[str]:
    return sorted(item["display"] for item in items)


async def test_two_scans_compared(make_api: ApiFactory) -> None:
    pages = Pages()
    api = await make_api({"test.pages": pages, "test.quiet": Quiet()})
    profile = await api.profile(("username", "jeanne"))

    pages.pages = {A: "v1", B: "v1"}
    first = await scanned(api, profile)
    pages.pages = {A: "v2", C: "v1"}
    second = await scanned(api, profile)

    diff = await api.json("GET", f"/profiles/{profile}/diff")
    assert (diff["before"]["id"], diff["after"]["id"]) == (first["id"], second["id"])
    assert displays(diff["new"]) == [C]
    assert displays(diff["gone"]) == [B]
    assert displays(diff["modified"]) == [A]
    assert diff["unchecked"] == []

    # A scan that didn't run the pages' search can't say they are gone.
    pages.pages = {}
    third = await scanned(api, profile, ["test.quiet"])
    diff = await api.json(
        "GET", f"/profiles/{profile}/diff?before={second['id']}&after={third['id']}"
    )
    assert displays(diff["gone"]) == []
    assert displays(diff["unchecked"]) == [A, C]


async def test_a_diff_needs_two_scans_in_order(make_api: ApiFactory) -> None:
    pages = Pages()
    api = await make_api({"test.pages": pages})
    profile = await api.profile(("username", "jeanne"))
    error = await api.json("GET", f"/profiles/{profile}/diff", status=409)
    assert error["code"] == "not_enough_scans"
    first = await scanned(api, profile)
    second = await scanned(api, profile)
    error = await api.json(
        "GET", f"/profiles/{profile}/diff?before={second['id']}&after={first['id']}", status=422
    )
    assert error["code"] == "scans_out_of_order"
    await api.json("GET", f"/profiles/{profile}/diff?after=999", status=404)


async def test_the_export_holds_everything_known_of_the_profile(make_api: ApiFactory) -> None:
    pages = Pages()
    api = await make_api({"test.pages": pages})
    profile = await api.profile(("name", "Jeanne Exemple"), ("username", "jeanne"))
    pages.pages = {A: "v1"}
    await scanned(api, profile)
    graph = await api.json("GET", f"/profiles/{profile}/graph")
    [page] = [n["id"] for n in graph["nodes"] if n["kind"] == "url"]
    await api.json("POST", f"/entities/{page}/requests", {"action": "ask_site"}, 201)

    data = await api.json("GET", f"/profiles/{profile}/export")

    assert (data["format"], data["version"]) == ("narcisse-export", 1)
    assert data["profile"]["name"] == "Jeanne Exemple"
    assert [s["value"] for s in data["profile"]["seeds"]] == ["Jeanne Exemple", "jeanne"]
    [trace] = [t for t in data["traces"] if t["display"] == A]
    assert trace["modules"] == ["test.pages"]
    assert trace["reasons"]["risk"]
    assert {e["entity_id"] for e in data["evidence"]} >= {trace["id"]}
    [scan] = data["scans"]
    assert scan["runs"]
    assert [r["action"] for r in data["requests"]] == ["ask_site"]
    assert len(data["history"]) == 1
    assert sum(data["exposure"]["levels"].values()) >= 1
    await api.json("GET", "/profiles/999/export", status=404)
