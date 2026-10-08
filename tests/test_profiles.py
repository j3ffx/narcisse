"""Profiles and seeds."""

from tests.conftest import Api


async def test_a_profile_with_its_seeds(api: Api) -> None:
    profile = await api.json(
        "POST",
        "/profiles",
        {"name": " Jeanne Exemple ", "kind": "mixed", "settings": {"pivot_depth": 1}},
        status=201,
    )
    assert profile["name"] == "Jeanne Exemple"
    assert profile["settings"] == {"pivot_depth": 1, "modules": []}
    url = f"/profiles/{profile['id']}/seeds"
    seed = await api.json("POST", url, {"kind": "email", "value": "Jeanne@Example.org"}, 201)
    assert seed["normalized"] == "jeanne@example.org"

    detail = await api.json("GET", f"/profiles/{profile['id']}")
    assert [s["id"] for s in detail["seeds"]] == [seed["id"]]


async def test_the_same_seed_twice_is_refused(api: Api) -> None:
    profile = await api.profile(("email", "jeanne@example.org"))
    error = await api.json(
        "POST", f"/profiles/{profile}/seeds", {"kind": "email", "value": "JEANNE@example.org"}, 409
    )
    assert error["code"] == "seed_exists"


async def test_a_seed_is_validated_for_its_kind(api: Api) -> None:
    profile = await api.profile()
    url = f"/profiles/{profile}/seeds"
    error = await api.json("POST", url, {"kind": "email", "value": "pas un email"}, 422)
    assert error == {"code": "invalid_value", "params": {"kind": "email"}}
    error = await api.json("POST", url, {"kind": "leak", "value": "x"}, 422)
    assert error["code"] == "invalid_seed_kind"


async def test_a_seed_can_be_edited_ignored_and_removed(api: Api) -> None:
    profile = await api.profile(("username", "jeanne"))
    seed = (await api.json("GET", f"/profiles/{profile}"))["seeds"][0]

    edited = await api.json(
        "PATCH", f"/seeds/{seed['id']}", {"value": "@Jeanne_E", "status": "ignore"}
    )
    assert (edited["value"], edited["normalized"], edited["status"]) == (
        "Jeanne_E",
        "jeanne_e",
        "ignore",
    )
    await api.json("DELETE", f"/seeds/{seed['id']}", status=204)
    assert (await api.json("GET", f"/profiles/{profile}"))["seeds"] == []


async def test_a_profile_is_renamed_and_deleted(api: Api) -> None:
    profile = await api.profile(("name", "Jeanne Exemple"))
    renamed = await api.json("PATCH", f"/profiles/{profile}", {"name": "Jeanne (pro)"})
    assert renamed["name"] == "Jeanne (pro)"
    await api.json("DELETE", f"/profiles/{profile}", status=204)
    assert await api.json("GET", "/profiles") == []


async def test_a_profile_being_scanned_cannot_be_deleted(api: Api) -> None:
    profile = await api.profile(("name", "Jeanne Exemple"))
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    await api.json("POST", f"/scans/{scan['id']}/pause", status=204)
    error = await api.json("DELETE", f"/profiles/{profile}", status=409)
    assert error["code"] == "profile_busy"
