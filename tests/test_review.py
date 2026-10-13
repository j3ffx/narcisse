"""Reviewing traces (it's me / not me), the run reports, the settings, and which sources each mode
offers."""

from typing import Any

from narcisse.config import Settings
from tests.conftest import Api, ApiFactory
from tests.fakes import Steps


async def finished_demo_scan(api: Api) -> tuple[int, int]:
    profile = await api.profile(("name", "Jeanne Exemple"))
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    await api.wait_scan(scan["id"], lambda s: s["status"] == "done")
    return profile, scan["id"]


async def test_a_trace_marked_not_me_leaves_the_results_until_asked_for(api: Api) -> None:
    profile, scan_id = await finished_demo_scan(api)
    results = (await api.json("GET", f"/scans/{scan_id}/results"))["items"]
    entity = results[0]["entity"]
    assert entity["status"] == "unreviewed"

    updated = await api.json("PATCH", f"/entities/{entity['id']}", {"status": "false_positive"})

    assert updated["status"] == "false_positive"
    remaining = await api.json("GET", f"/scans/{scan_id}/results")
    assert entity["id"] not in [r["entity"]["id"] for r in remaining["items"]]
    everything = await api.json("GET", f"/scans/{scan_id}/results?false_positives=true")
    assert everything["total"] == remaining["total"] + 1
    events = await api.app.state.services.bus.read_after(0, limit=10_000)
    [event] = [e for e in events if e.type == "entity.updated"]
    assert event.payload["status"] == "false_positive"
    assert event.payload["profile_id"] == profile


async def test_a_review_holds_for_the_next_scans(api: Api) -> None:
    profile, scan_id = await finished_demo_scan(api)
    first = (await api.json("GET", f"/scans/{scan_id}/results"))["items"][0]["entity"]
    await api.json("PATCH", f"/entities/{first['id']}", {"status": "confirmed"})

    again = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    await api.wait_scan(again["id"], lambda s: s["status"] == "done")

    items = (await api.json("GET", f"/scans/{again['id']}/results"))["items"]
    [same] = [r["entity"] for r in items if r["entity"]["id"] == first["id"]][:1]
    assert same["status"] == "confirmed"


async def test_the_identity_itself_is_not_up_for_review(api: Api) -> None:
    await finished_demo_scan(api)
    error = await api.json("PATCH", "/entities/1", {"status": "false_positive"}, status=409)
    assert error["code"] == "entity_not_reviewable"


async def test_a_run_keeps_what_its_module_reported(make_api: ApiFactory) -> None:
    module = Steps(steps=3, delay=1)
    api = await make_api({module.meta.name: module})
    profile = await api.profile(("name", "Jeanne Exemple"))
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    done = await api.wait_scan(scan["id"], lambda s: s["status"] == "done")
    assert done["runs"][0]["notes"] == {"checked": 3}


async def test_settings_keep_the_tokens_without_ever_showing_them(
    api: Api, settings: Settings
) -> None:
    nothing = {
        "github_token_set": False,
        "gitlab_token_set": False,
        "exclude_adult": False,
        "fediverse_instances": [],
        "searxng_url": None,
        "enabled_light_active": [],
    }
    assert await api.json("GET", "/preferences") == nothing
    shown: Any = await api.json(
        "PATCH",
        "/preferences",
        {"github_token": " ghp_test ", "gitlab_token": "glpat-test", "exclude_adult": True},
    )
    assert shown == {
        **nothing,
        "github_token_set": True,
        "gitlab_token_set": True,
        "exclude_adult": True,
    }
    assert "ghp_test" not in str(shown)
    assert "glpat" not in str(shown)
    assert '"github_token": "ghp_test"' in settings.preferences_path.read_text(encoding="utf-8")

    cleared = await api.json("PATCH", "/preferences", {"github_token": "", "gitlab_token": None})
    assert cleared == {**nothing, "exclude_adult": True}


async def test_settings_remember_which_light_active_sources_are_on(make_api: ApiFactory) -> None:
    api = await make_api(None, demo=False)
    shown = await api.json(
        "PATCH",
        "/preferences",
        {"enabled_light_active": ["example_check", "example_check", " ", "other"]},
    )
    assert shown["enabled_light_active"] == ["example_check", "other"]
    assert (await api.json("GET", "/preferences"))["enabled_light_active"] == [
        "example_check",
        "other",
    ]
    emptied = await api.json("PATCH", "/preferences", {"enabled_light_active": []})
    assert emptied["enabled_light_active"] == []


async def test_settings_keep_fediverse_instances_as_host_names(make_api: ApiFactory) -> None:
    api = await make_api(None, demo=False)
    shown = await api.json(
        "PATCH",
        "/preferences",
        {"fediverse_instances": ["https://Social.Example.org/@jeanne", "social.example.org", " "]},
    )
    assert shown["fediverse_instances"] == ["social.example.org"]
    hosts = {m["name"]: m["hosts"] for m in await api.json("GET", "/modules")}
    assert "social.example.org" in hosts["fediverse"]
    assert "social.example.org" not in hosts["github"]

    await api.json("PATCH", "/preferences", {"fediverse_instances": ["pas un domaine"]}, status=422)


async def test_each_mode_offers_its_own_sources(make_api: ApiFactory) -> None:
    normal = [m["name"] for m in await (await make_api(None, demo=False)).json("GET", "/modules")]
    demo = [m["name"] for m in await (await make_api(None, demo=True)).json("GET", "/modules")]
    assert demo == ["demo.fake"]  # fictitious identities never reach real sites
    assert {"whatsmyname", "github", "gravatar", "pgp", "fediverse"} <= set(normal)
    assert {"registration", "dns", "certificates", "website"} <= set(normal)
    assert "demo.fake" not in normal


async def test_the_sources_say_which_hosts_they_learn_when_they_run(make_api: ApiFactory) -> None:
    api = await make_api(None, demo=False)
    modules = {m["name"]: m for m in await api.json("GET", "/modules")}
    # The site of the domain searched: known only then.
    assert modules["website"]["hosts"] == []
    assert modules["website"]["other_hosts"] == "le site du domaine fouillé (et son www.)"
    assert modules["github"]["other_hosts"] == ""
