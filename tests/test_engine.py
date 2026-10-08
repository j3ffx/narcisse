"""The scan engine, through the API the UI uses."""

import asyncio
from typing import Any

from narcisse.domain import RunStatus
from narcisse.modules.demo import STEPS
from tests.conftest import Api, ApiFactory
from tests.fakes import Crashes, OneAtATime, Rejects, Steps

JEANNE = (
    ("name", "Jeanne Exemple"),
    ("username", "jeanne.exemple"),
    ("email", "jeanne.exemple@example.org"),
    ("domain", "jeanne-exemple.example.org"),
)


def finished(scan: Any) -> bool:
    return bool(scan["status"] in ("done", "cancelled"))


def runs_by_kind(scan: Any) -> dict[str, Any]:
    return {run["input_kind"]: run for run in scan["runs"]}


async def events_of(api: Api, type_: str) -> list[dict[str, Any]]:
    events = await api.app.state.services.bus.read_after(0, limit=100_000)
    return [e.payload for e in events if e.type == type_]


async def start(api: Api, profile_id: int, *modules: str) -> int:
    scan = await api.json(
        "POST", f"/profiles/{profile_id}/scans", {"modules": list(modules)}, status=201
    )
    return int(scan["id"])


async def test_the_demo_scan_shows_every_state_then_finishes(api: Api) -> None:
    profile = await api.profile(*JEANNE)
    scan_id = await start(api, profile, "demo.fake")

    scan = await api.wait_scan(scan_id, finished)

    runs = runs_by_kind(scan)
    assert scan["status"] == "done"
    assert runs["name"]["status"] == "done"
    assert runs["name"]["results_count"] == STEPS
    # The username's run waited for a rate limit, then went on from where it stopped.
    assert runs["username"]["status"] == "done"
    assert runs["username"]["results_count"] == STEPS
    statuses = [
        (e["input_kind"], e["status"], e["error_code"]) for e in await events_of(api, "run.updated")
    ]
    assert ("username", "rate_limited", "rate_limited") in statuses
    # The e-mail's run hit a transient error and was retried by the engine alone.
    assert ("email", "queued", "network_error") in statuses
    assert runs["email"]["status"] == "done"
    assert runs["email"]["attempts"] == 2
    # The domain's run failed, and says why.
    assert runs["domain"]["status"] == "failed"
    assert runs["domain"]["error_code"] == "source_unavailable"
    assert runs["domain"]["retryable"] is True
    assert scan["results_count"] == 3 * STEPS + 4


async def test_a_failed_run_can_be_retried_and_reopens_the_scan(api: Api) -> None:
    profile = await api.profile(("domain", "jeanne-exemple.example.org"))
    scan_id = await start(api, profile, "demo.fake")
    scan = await api.wait_scan(scan_id, finished)
    run = scan["runs"][0]
    assert run["status"] == "failed"

    await api.json("POST", f"/runs/{run['id']}/retry", status=204)

    scan = await api.wait_scan(
        scan_id, lambda s: s["status"] == "done" and s["runs"][0]["status"] == "done"
    )
    assert scan["runs"][0]["results_count"] == STEPS


async def test_results_arrive_one_by_one_as_events(api: Api) -> None:
    profile = await api.profile(("name", "Jeanne Exemple"))
    scan_id = await start(api, profile, "demo.fake")
    await api.wait_scan(scan_id, finished)

    results = await events_of(api, "result.created")
    assert len(results) == STEPS
    assert len({r["id"] for r in results}) == STEPS
    page = await api.json("GET", f"/scans/{scan_id}/results?limit=5")
    assert page["total"] == STEPS
    assert [r["id"] for r in page["items"]] == [r["id"] for r in results[:5]]
    accounts = await api.json("GET", f"/scans/{scan_id}/results?kind=account")
    assert accounts["total"] == 6


async def test_pause_holds_every_run_and_resume_finishes_them(make_api: ApiFactory) -> None:
    module = Steps(steps=8, delay=20)
    api = await make_api({module.meta.name: module})
    profile = await api.profile(("name", "Jeanne Exemple"), ("username", "jeanne"))
    scan_id = await start(api, profile)
    await api.wait_scan(scan_id, lambda s: s["results_count"] >= 2)

    await api.json("POST", f"/scans/{scan_id}/pause", status=204)

    paused = await api.scan(scan_id)
    assert paused["status"] == "paused"
    assert {r["status"] for r in paused["runs"]} == {"paused"}
    await asyncio.sleep(0.4)  # four steps' worth
    later = await api.scan(scan_id)
    # A run may finish the step it was in; none starts another.
    assert later["results_count"] <= paused["results_count"] + len(paused["runs"])

    await api.json("POST", f"/scans/{scan_id}/resume", status=204)

    scan = await api.wait_scan(scan_id, finished)
    assert scan["status"] == "done"
    assert scan["results_count"] == 16


async def test_cancel_stops_every_run_for_good(make_api: ApiFactory) -> None:
    module = Steps(steps=50, delay=20)
    api = await make_api({module.meta.name: module})
    profile = await api.profile(("name", "Jeanne Exemple"), ("email", "jeanne@example.org"))
    scan_id = await start(api, profile)
    await api.wait_scan(scan_id, lambda s: s["results_count"] >= 1)

    await api.json("POST", f"/scans/{scan_id}/cancel", status=204)

    scan = await api.scan(scan_id)
    assert scan["status"] == "cancelled"
    assert {r["status"] for r in scan["runs"]} == {"cancelled"}
    await asyncio.sleep(0.3)
    assert (await api.scan(scan_id))["results_count"] == scan["results_count"]
    await api.json("POST", f"/scans/{scan_id}/resume", status=409)


async def test_a_restart_resumes_running_scans_from_their_checkpoints(
    make_api: ApiFactory,
) -> None:
    first = Steps(steps=10, delay=20)
    api = await make_api({first.meta.name: first})
    profile = await api.profile(("name", "Jeanne Exemple"))
    scan_id = await start(api, profile)
    await api.wait_scan(scan_id, lambda s: s["results_count"] >= 3)
    await api.stop()

    second = Steps(steps=10, delay=20)
    api = await make_api({second.meta.name: second})
    scan = await api.wait_scan(scan_id, finished)

    assert scan["status"] == "done"
    assert scan["results_count"] == 10  # nothing lost, nothing twice
    assert second.started_at_step[0] >= 3
    assert scan["runs"][0]["attempts"] == 1  # a restart is not a failed attempt


async def test_a_paused_scan_stays_paused_across_a_restart(make_api: ApiFactory) -> None:
    first = Steps(steps=6, delay=20)
    api = await make_api({first.meta.name: first})
    profile = await api.profile(("name", "Jeanne Exemple"))
    scan_id = await start(api, profile)
    await api.wait_scan(scan_id, lambda s: s["results_count"] >= 1)
    await api.json("POST", f"/scans/{scan_id}/pause", status=204)
    await api.stop()

    second = Steps(steps=6, delay=20)
    api = await make_api({second.meta.name: second})
    await asyncio.sleep(0.3)
    assert (await api.scan(scan_id))["status"] == "paused"
    assert second.started_at_step == []

    await api.json("POST", f"/scans/{scan_id}/resume", status=204)
    scan = await api.wait_scan(scan_id, finished)
    assert scan["results_count"] == 6


async def test_a_module_never_runs_more_at_once_than_it_allows(make_api: ApiFactory) -> None:
    module = OneAtATime(steps=3, delay=5)
    api = await make_api({module.meta.name: module})
    profile = await api.profile(
        ("name", "Jeanne"), ("username", "jeanne"), ("email", "j@example.org")
    )
    scan_id = await start(api, profile)

    scan = await api.wait_scan(scan_id, finished)

    assert scan["status"] == "done"
    assert module.max_running == 1


async def test_a_crashing_module_fails_with_a_message_not_a_trace(make_api: ApiFactory) -> None:
    modules = {Crashes.meta.name: Crashes(), Rejects.meta.name: Rejects()}
    api = await make_api(modules)
    profile = await api.profile(("name", "Jeanne Exemple"))
    scan_id = await start(api, profile)

    scan = await api.wait_scan(scan_id, finished)

    runs = {r["module"]: r for r in scan["runs"]}
    assert runs["test.crashes"]["error_code"] == "module_crashed"
    assert runs["test.crashes"]["retryable"] is True
    assert runs["test.rejects"]["error_code"] == "input_rejected"
    assert runs["test.rejects"]["retryable"] is False
    await api.json("POST", f"/runs/{runs['test.rejects']['id']}/retry", status=409)


async def test_a_module_gone_after_a_restart_fails_its_runs(make_api: ApiFactory) -> None:
    module = Steps(steps=20, delay=20)
    api = await make_api({module.meta.name: module})
    profile = await api.profile(("name", "Jeanne Exemple"))
    scan_id = await start(api, profile)
    await api.wait_scan(scan_id, lambda s: s["results_count"] >= 1)
    await api.stop()

    api = await make_api({})
    scan = await api.wait_scan(scan_id, finished)

    assert scan["runs"][0]["status"] == RunStatus.FAILED
    assert scan["runs"][0]["error_code"] == "module_unavailable"


async def test_a_scan_needs_seeds_and_known_modules(api: Api) -> None:
    empty = await api.profile()
    error = await api.json("POST", f"/profiles/{empty}/scans", {}, status=409)
    assert error == {"code": "no_seeds", "params": {}}

    profile = await api.profile(("name", "Jeanne Exemple"), name="Autre")
    error = await api.json("POST", f"/profiles/{profile}/scans", {"modules": ["nope"]}, status=422)
    assert error["code"] == "unknown_module"


async def test_ignored_seeds_are_not_scanned(api: Api) -> None:
    profile = await api.profile(("name", "Jeanne Exemple"))
    seed = await api.json(
        "POST",
        f"/profiles/{profile}/seeds",
        {"kind": "username", "value": "jeanne", "status": "ignore"},
        201,
    )
    assert seed["status"] == "ignore"
    scan_id = await start(api, profile, "demo.fake")
    scan = await api.scan(scan_id)
    assert [r["input_kind"] for r in scan["runs"]] == ["name"]
