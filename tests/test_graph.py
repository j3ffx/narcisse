"""How traces relate: each result says which trace it was read on."""

from tests.conftest import Api, ApiFactory
from tests.fakes import Profiles


async def scanned(make_api: ApiFactory) -> tuple[Api, int, int]:
    api = await make_api({"test.profiles": Profiles()})
    profile = await api.profile(("username", "jeanne"))
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    await api.wait_scan(scan["id"], lambda s: s["status"] == "done")
    return api, profile, scan["id"]


async def test_each_live_result_carries_its_edge(make_api: ApiFactory) -> None:
    api, profile, scan_id = await scanned(make_api)
    results = (await api.json("GET", f"/scans/{scan_id}/results"))["items"]
    site = next(r for r in results if r["entity"]["display"] == "https://jeanne.example.org")
    account = next(r for r in results if r["relation"] == "has_account")
    assert site["profile_id"] == profile
    assert site["edge"]["source_id"] == account["entity"]["id"]
    assert site["edge"]["target_id"] == site["entity"]["id"]
