"""A profile's traces as a graph, and one trace in detail."""

from typing import Any

from tests.conftest import Api, ApiFactory
from tests.fakes import Profiles


async def scanned(make_api: ApiFactory) -> tuple[Api, int, int]:
    api = await make_api({"test.profiles": Profiles()})
    profile = await api.profile(("username", "jeanne"))
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    await api.wait_scan(scan["id"], lambda s: s["status"] == "done")
    return api, profile, scan["id"]


def by_display(graph: Any) -> dict[str, Any]:
    """Nodes by "kind:display" (the identity and a name may read the same)."""
    return {f"{n['kind']}:{n['display']}": n for n in graph["nodes"]}


async def test_the_graph_relates_each_trace_to_the_one_it_was_read_on(
    make_api: ApiFactory,
) -> None:
    api, profile, _ = await scanned(make_api)
    graph = await api.json("GET", f"/profiles/{profile}/graph")
    nodes = by_display(graph)
    ids = {n["id"]: name for name, n in nodes.items()}
    edges = {(ids[e["source_id"]], e["relation"], ids[e["target_id"]]) for e in graph["edges"]}

    account = "account:https://social.example.org/@jeanne"
    assert edges == {
        ("identity:Jeanne Exemple", "declares", "username:jeanne"),
        ("username:jeanne", "has_account", account),
        (account, "links_to", "url:https://jeanne.example.org"),
        (account, "shows_name", "name:Jeanne Exemple"),
        # Said to be read on a trace that was never found: the target stands in.
        ("username:jeanne", "shows_email", "email:jeanne@example.org"),
    }
    assert graph["truncated"] is False
    assert nodes["username:jeanne"]["modules"] == ["seed"]
    assert nodes[account]["modules"] == ["test.profiles"]
    assert nodes[account]["evidence_count"] == 1


async def test_a_trace_marked_not_me_leaves_the_graph_until_asked_for(
    make_api: ApiFactory,
) -> None:
    api, profile, _ = await scanned(make_api)
    site = by_display(await api.json("GET", f"/profiles/{profile}/graph"))[
        "url:https://jeanne.example.org"
    ]
    await api.json("PATCH", f"/entities/{site['id']}", {"status": "false_positive"})

    graph = await api.json("GET", f"/profiles/{profile}/graph")
    assert site["id"] not in [n["id"] for n in graph["nodes"]]
    assert all(site["id"] not in (e["source_id"], e["target_id"]) for e in graph["edges"])
    everything = await api.json("GET", f"/profiles/{profile}/graph?false_positives=true")
    assert site["id"] in [n["id"] for n in everything["nodes"]]


async def test_a_trace_in_detail_shows_its_proofs_and_neighbours(make_api: ApiFactory) -> None:
    api, profile, scan_id = await scanned(make_api)
    account = by_display(await api.json("GET", f"/profiles/{profile}/graph"))[
        "account:https://social.example.org/@jeanne"
    ]
    detail = await api.json("GET", f"/entities/{account['id']}")

    assert detail["entity"]["id"] == account["id"]
    assert [(p["module"], p["relation"], p["scan_id"]) for p in detail["evidence"]] == [
        ("test.profiles", "has_account", scan_id)
    ]
    assert sorted(n["display"] for n in detail["neighbours"]) == [
        "Jeanne Exemple",
        "https://jeanne.example.org",
        "jeanne",
    ]
    assert len(detail["edges"]) == 3
    await api.json("GET", "/entities/999999", status=404)
    await api.json("GET", "/profiles/999999/graph", status=404)


async def test_each_live_result_carries_its_edge(make_api: ApiFactory) -> None:
    api, profile, scan_id = await scanned(make_api)
    results = (await api.json("GET", f"/scans/{scan_id}/results"))["items"]
    site = next(r for r in results if r["entity"]["display"] == "https://jeanne.example.org")
    account = next(r for r in results if r["relation"] == "has_account")
    assert site["profile_id"] == profile
    assert site["edge"]["source_id"] == account["entity"]["id"]
    assert site["edge"]["target_id"] == site["entity"]["id"]


async def test_demo_mode_makes_a_fictitious_graph_of_the_size_asked(api: Api) -> None:
    made = await api.json("POST", "/demo/graph", {"nodes": 500}, status=201)
    graph = await api.json("GET", f"/profiles/{made['profile_id']}/graph?false_positives=true")

    assert 500 <= len(graph["nodes"]) < 520
    assert len(graph["edges"]) >= len(graph["nodes"]) - 1  # everything hangs together
    ids = {n["id"] for n in graph["nodes"]}
    assert all(e["source_id"] in ids and e["target_id"] in ids for e in graph["edges"])
    # Chains, not a star: traces found on accounts, and traces found twice.
    kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
    assert any(kinds[e["source_id"]] == "account" for e in graph["edges"])
    targets = [e["target_id"] for e in graph["edges"]]
    assert len(set(targets)) < len(targets)
    hosts = {n["display"].split("/")[2] for n in graph["nodes"] if n["kind"] == "account"}
    assert all(".example." in host for host in hosts)  # reserved domains only
    profile = await api.json("GET", f"/profiles/{made['profile_id']}")
    assert len(profile["seeds"]) == 9


async def test_only_demo_mode_makes_fictitious_graphs(make_api: ApiFactory) -> None:
    api = await make_api(None, demo=False)
    await api.json("POST", "/demo/graph", {"nodes": 100}, status=404)
