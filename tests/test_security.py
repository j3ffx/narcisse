"""Another website open in the browser must not read or drive the local server."""

import pytest

from tests.conftest import Api


@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1.evil.example", "192.168.1.10:8765"])
async def test_a_foreign_host_is_refused(api: Api, host: str) -> None:
    response = await api.client.get("/api/profiles", headers={"Host": host})
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden_host"


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "[::1]:8765", "localhost"])
async def test_loopback_hosts_are_served(api: Api, host: str) -> None:
    response = await api.client.get("/api/profiles", headers={"Host": host})
    assert response.status_code == 200


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://127.0.0.1:9999"])
async def test_a_foreign_origin_cannot_change_anything(api: Api, origin: str) -> None:
    response = await api.client.post(
        "/api/profiles", json={"name": "Jeanne Exemple"}, headers={"Origin": origin}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden_origin"
    assert (await api.json("GET", "/profiles")) == []


async def test_the_own_origin_and_scripts_without_origin_can(api: Api) -> None:
    await api.json("POST", "/profiles", {"name": "Sans origine"}, status=201)
    response = await api.client.post(
        "/api/profiles", json={"name": "Même origine"}, headers={"Origin": "http://127.0.0.1:8765"}
    )
    assert response.status_code == 201


async def test_a_form_post_is_refused(api: Api) -> None:
    # What a cross-site <form> can send without a CORS preflight.
    response = await api.client.post(
        "/api/profiles",
        content=b"name=Jeanne",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 415
    assert response.json()["code"] == "json_required"


async def test_no_cors_is_granted(api: Api) -> None:
    response = await api.client.options(
        "/api/profiles",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers


async def test_errors_are_codes_without_traces(api: Api) -> None:
    response = await api.client.get("/api/profiles/999")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "params": {"what": "profile"}}
    response = await api.client.post("/api/profiles", json={"name": ""})
    assert response.status_code == 422
    assert response.json() == {"code": "invalid_request", "params": {"fields": ["name"]}}
    response = await api.client.get("/api/nope")
    assert response.json()["code"] == "not_found"
