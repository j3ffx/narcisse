"""Another website open in the browser must not read or drive the local server."""

import pytest

from narcisse.config import maps_to_loopback
from tests.conftest import Api, ApiFactory


@pytest.mark.parametrize(
    "host",
    ["evil.example", "127.0.0.1.evil.example", "localhost.evil.example", "192.168.1.10:8765"],
)
async def test_a_foreign_host_is_refused(api: Api, host: str) -> None:
    response = await api.client.get("/api/profiles", headers={"Host": host})
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden_host"


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1:8765", "localhost:8765", "[::1]:8765", "localhost", "narcisse.localhost:8765"],
)
async def test_loopback_hosts_are_served(api: Api, host: str) -> None:
    response = await api.client.get("/api/profiles", headers={"Host": host})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "origin",
    ["https://evil.example", "null", "http://127.0.0.1:9999", "http://narcisse.localhost:8765"],
)
async def test_a_foreign_origin_cannot_change_anything(api: Api, origin: str) -> None:
    response = await api.client.post(
        "/api/profiles", json={"name": "Jeanne Exemple"}, headers={"Origin": origin}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden_origin"
    assert (await api.json("GET", "/profiles")) == []


@pytest.mark.parametrize("origin", ["http://narcisse.localhost", "http://127.0.0.1"])
async def test_the_own_origin_and_scripts_without_origin_can(api: Api, origin: str) -> None:
    await api.json("POST", "/profiles", {"name": "Sans origine"}, status=201)
    response = await api.client.post(
        "/api/profiles", json={"name": "Même origine"}, headers={"Origin": origin}
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


def test_the_short_name_counts_only_when_the_hosts_file_maps_it() -> None:
    assert maps_to_loopback("127.0.0.1 narcisse\n", "narcisse")
    assert maps_to_loopback("# local\n::1   other narcisse  # Narcisse\n", "narcisse")
    assert not maps_to_loopback("# 127.0.0.1 narcisse\n", "narcisse")
    assert not maps_to_loopback("192.168.1.10 narcisse\n", "narcisse")
    assert not maps_to_loopback("127.0.0.1 narcisse.example.org\n", "narcisse")


@pytest.mark.parametrize(("short_host", "status"), [(False, 403), (True, 200)])
async def test_the_short_name_is_served_only_once_mapped(
    make_api: ApiFactory, short_host: bool, status: int
) -> None:
    api = await make_api(None, short_host=short_host)
    response = await api.client.get("/api/profiles", headers={"Host": "narcisse"})
    assert response.status_code == status
