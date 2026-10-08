"""The live stream: a browser that reconnects gets exactly what it missed, in order."""

import json
from typing import Any

import httpx

from tests.conftest import Api

Event = tuple[int | None, str, Any]


async def read_events(base: str, count: int, **headers: str) -> list[Event]:
    """Reads the stream until `count` events (comments skipped) have come."""
    events: list[Event] = []
    async with (
        httpx.AsyncClient(base_url=base, timeout=10) as client,
        client.stream("GET", "/api/events", headers=headers) as response,
    ):
        assert response.headers["content-type"].startswith("text/event-stream")
        event_id, kind, data = None, "message", None
        async for line in response.aiter_lines():
            if line.startswith("id: "):
                event_id = int(line[4:])
            elif line.startswith("event: "):
                kind = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
            elif line == "" and data is not None:
                events.append((event_id, kind, data))
                event_id, kind, data = None, "message", None
                if len(events) == count:
                    return events
    return events


async def run_demo_scan(base: str) -> int:
    async with httpx.AsyncClient(base_url=f"{base}/api") as client:
        profile = (await client.post("/profiles", json={"name": "Jeanne Exemple"})).json()
        await client.post(
            f"/profiles/{profile['id']}/seeds", json={"kind": "name", "value": "Jeanne Exemple"}
        )
        scan = (await client.post(f"/profiles/{profile['id']}/scans", json={})).json()
        return int(scan["id"])


async def test_events_stream_live_then_replay_from_the_last_seen(live_server: str) -> None:
    await run_demo_scan(live_server)
    first = await read_events(live_server, 10)
    ids = [e[0] or 0 for e in first]
    assert all(ids)
    assert ids == sorted(ids)
    assert first[0][1] == "scan.created"

    # Reconnecting as EventSource does, with the last id it saw.
    resumed = await read_events(live_server, 5, **{"Last-Event-ID": str(ids[4])})
    assert [e[0] for e in resumed] == ids[5:10]


async def test_a_client_ahead_of_the_server_is_told_to_reload(live_server: str) -> None:
    events = await read_events(live_server, 1, **{"Last-Event-ID": "999999"})
    assert events[0][1] == "reset"


async def test_the_activity_snapshot_says_which_event_it_includes(api: Api) -> None:
    profile = await api.profile(("name", "Jeanne Exemple"))
    await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    activity = await api.json("GET", "/activity")
    assert activity["last_event_id"] >= 1
    assert activity["scans"][0]["profile_name"] == "Jeanne Exemple"
    assert activity["scans"][0]["runs"][0]["input_value"] == "Jeanne Exemple"
