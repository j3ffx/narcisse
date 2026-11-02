"""The first steps: the welcome page's choice, kept, and starting again on the other side."""

from tests.conftest import Api, ApiFactory


async def test_the_welcome_page_is_seen_once(api: Api) -> None:
    assert (await api.json("GET", "/preferences"))["welcomed"] is False
    await api.json("PATCH", "/preferences", {"welcomed": True})
    assert (await api.json("GET", "/preferences"))["welcomed"] is True


async def test_a_terminal_cannot_switch_sides(api: Api) -> None:
    assert (await api.json("GET", "/info"))["can_switch"] is False
    answer = await api.json("POST", "/side", {}, status=409)
    assert answer["code"] == "side_unavailable"


async def test_the_tray_switches_sides_when_asked(make_api: ApiFactory) -> None:
    asked: list[bool] = []
    api = await make_api(switch_side=lambda: asked.append(True))
    assert (await api.json("GET", "/info"))["can_switch"] is True
    await api.json("POST", "/side", {}, status=202)
    assert asked == [True]
