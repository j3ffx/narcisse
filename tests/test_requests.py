"""Following what the user did about a trace: its status, the reminder a month after sending,
the scans that look for the trace again, and the exposure over time."""

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any, ClassVar

from sqlalchemy import update

from narcisse.domain import EntityKind
from narcisse.engine.plugin import Finding, ModuleContext, ModuleMeta, SourceModule, Target
from narcisse.storage.models import RemovalRequest
from tests.conftest import Api, ApiFactory
from tests.fakes import meta

PAGE = "https://annuaire.example.org/jeanne"


class Directory(SourceModule):
    """A directory that lists the user while `listed` is true (the user's request removes it)."""

    meta: ClassVar[ModuleMeta] = meta("test.directory")

    def __init__(self) -> None:
        self.listed = True

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(0, 1)
        if self.listed:
            yield Finding(
                kind=EntityKind.URL, value=PAGE, relation="mentioned_on", url=PAGE, confidence=0.9
            )


async def scanned(api: Api, profile: int) -> dict[str, Any]:
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    done: dict[str, Any] = await api.wait_scan(scan["id"], lambda s: s["status"] == "done")
    return done


async def page_trace(api: Api, profile: int) -> int:
    graph = await api.json("GET", f"/profiles/{profile}/graph")
    [page] = [n["id"] for n in graph["nodes"] if n["kind"] == "url"]
    return int(page)


async def setup(make_api: ApiFactory) -> tuple[Api, Directory, int, int]:
    directory = Directory()
    api = await make_api({"test.directory": directory})
    profile = await api.profile(("name", "Jeanne Exemple"), ("email", "jeanne@example.org"))
    await scanned(api, profile)
    return api, directory, profile, await page_trace(api, profile)


async def test_an_action_is_followed_from_the_sheet(make_api: ApiFactory) -> None:
    api, _, profile, page = await setup(make_api)

    todo = await api.json(
        "POST", f"/entities/{page}/requests", {"action": "ask_site", "letter": "erasure"}, 201
    )
    assert (todo["status"], todo["sent_at"], todo["due"]) == ("todo", None, False)
    sent = await api.json(
        "POST",
        f"/entities/{page}/requests",
        {
            "action": "ask_site",
            "letter": "erasure",
            "recipient": "contact@annuaire.example.org",
            "subject": "Effacement",
            "body": "Merci d’effacer cette page.",
            "status": "sent",
        },
        201,
    )
    # The same action on the same site: one request, updated.
    assert sent["id"] == todo["id"]
    assert sent["status"] == "sent"
    assert sent["sent_at"] is not None
    assert sent["reminder_at"] is not None

    sheet = await api.json("GET", f"/entities/{page}/remediation")
    [ask] = [a for a in sheet["actions"] if a["code"] == "ask_site"]
    assert ask["request"]["id"] == sent["id"]
    assert [r["id"] for r in await api.json("GET", f"/profiles/{profile}/requests")] == [sent["id"]]


async def test_statuses_keep_their_dates(make_api: ApiFactory) -> None:
    api, _, _, page = await setup(make_api)
    request = await api.json(
        "POST", f"/entities/{page}/requests", {"action": "ask_site", "status": "sent"}, 201
    )
    refused = await api.json(
        "PATCH", f"/requests/{request['id']}", {"status": "refused", "note": " Pas de suite. "}
    )
    assert refused["closed_at"] is not None
    assert refused["note"] == "Pas de suite."
    again = await api.json("PATCH", f"/requests/{request['id']}", {"status": "waiting"})
    assert again["closed_at"] is None
    assert again["sent_at"] == request["sent_at"]
    await api.json("DELETE", f"/requests/{request['id']}", status=204)
    await api.json("PATCH", f"/requests/{request['id']}", {"status": "done"}, status=404)


async def test_a_request_unanswered_for_a_month_is_due_for_a_reminder(
    make_api: ApiFactory,
) -> None:
    api, _, profile, page = await setup(make_api)
    request = await api.json(
        "POST",
        f"/entities/{page}/requests",
        {
            "action": "ask_site",
            "letter": "erasure",
            "subject": "Effacement de mes données",
            "body": "Merci d’effacer cette page.",
            "status": "sent",
        },
        201,
    )
    assert (await api.json("GET", "/requests/due"))["count"] == 0

    services = api.app.state.services
    long_ago = services.engine.clock.now() - timedelta(days=31)
    async with services.db.write() as session:
        await session.execute(
            update(RemovalRequest)
            .where(RemovalRequest.id == request["id"])
            .values(sent_at=long_ago)
        )

    [due] = await api.json("GET", f"/profiles/{profile}/requests")
    assert due["due"] is True
    assert (await api.json("GET", "/requests/due"))["count"] == 1
    reminder = await api.json("GET", f"/requests/{request['id']}/reminder")
    assert reminder["fr"]["subject"] == "Relance : Effacement de mes données"
    assert "article 12.3" in reminder["fr"]["body"]
    assert reminder["fr"]["body"].endswith("Merci d’effacer cette page.")
    assert "Jeanne Exemple\njeanne@example.org" in reminder["en"]["body"]

    # Reminded: due again a month later, not before.
    reminded = await api.json("PATCH", f"/requests/{request['id']}", {"reminded": True})
    assert reminded["due"] is False
    assert reminded["reminded_at"] is not None


async def test_a_reminder_needs_a_sent_request(make_api: ApiFactory) -> None:
    api, _, _, page = await setup(make_api)
    request = await api.json("POST", f"/entities/{page}/requests", {"action": "ask_site"}, 201)
    error = await api.json("GET", f"/requests/{request['id']}/reminder", status=409)
    assert error["code"] == "request_not_sent"


async def test_a_check_finds_the_trace_gone_and_closes_the_request(make_api: ApiFactory) -> None:
    api, directory, profile, page = await setup(make_api)
    request = await api.json(
        "POST", f"/entities/{page}/requests", {"action": "ask_site", "status": "sent"}, 201
    )

    # Still listed: the check says so, and the request stays open.
    check = await api.json("POST", f"/requests/{request['id']}/check", {}, 201)
    assert check["notes"]["check"] == request["id"]
    # The searches that found it: the directory, from each element it was found from.
    assert [(r["module"], r["input_kind"]) for r in check["runs"]] == [
        ("test.directory", "name"),
        ("test.directory", "email"),
    ]
    await api.wait_scan(check["id"], lambda s: s["status"] == "done")
    [still] = await api.json("GET", f"/profiles/{profile}/requests")
    assert (still["check"], still["status"]) == ("still_there", "sent")

    # The site removed it: any scan running the same search sees it gone.
    directory.listed = False
    await scanned(api, profile)
    [gone] = await api.json("GET", f"/profiles/{profile}/requests")
    assert (gone["check"], gone["status"]) == ("gone", "done")
    assert gone["closed_at"] is not None
    assert gone["due"] is False

    exposure = await api.json("GET", f"/profiles/{profile}/exposure")
    assert exposure["gone"] == 1
    assert exposure["requests"]["done"] == 1
    # One snapshot per finished scan: the first scan, the check, the last scan.
    assert len(exposure["history"]) == 3
    first, _, last = exposure["history"]
    assert last["exposure"] < first["exposure"]
    assert sum(last["levels"].values()) == sum(first["levels"].values()) - 1


async def test_a_trace_found_by_no_search_cannot_be_checked(api: Api) -> None:
    profile = await api.profile(("name", "Jeanne Exemple"))
    trace = await api.json(
        "POST", f"/profiles/{profile}/traces", {"url": "https://blog.example.org/x"}, 201
    )
    request = await api.json(
        "POST", f"/entities/{trace['id']}/requests", {"action": "ask_site"}, 201
    )
    error = await api.json("POST", f"/requests/{request['id']}/check", {}, status=409)
    assert error["code"] == "nothing_to_check"


async def test_any_trace_no_scan_finds_any_more_is_gone_until_found_again(
    make_api: ApiFactory,
) -> None:
    api, directory, profile, page = await setup(make_api)

    directory.listed = False
    await scanned(api, profile)
    graph = await api.json("GET", f"/profiles/{profile}/graph")
    [node] = [n for n in graph["nodes"] if n["id"] == page]
    assert node["gone_at"] is not None
    assert (await api.json("GET", f"/profiles/{profile}/exposure"))["gone"] == 1

    directory.listed = True
    await scanned(api, profile)
    detail = await api.json("GET", f"/entities/{page}")
    assert detail["entity"]["gone_at"] is None


async def test_a_trace_whose_searches_did_not_all_run_again_is_not_gone(
    make_api: ApiFactory,
) -> None:
    directory = Directory()
    api = await make_api({"test.directory": directory, "test.other": Other()})
    profile = await api.profile(("name", "Jeanne Exemple"))
    await scanned(api, profile)
    page = await page_trace(api, profile)

    # Only the other source runs: the directory's search didn't run again, nothing is said.
    directory.listed = False
    scan = await api.json(
        "POST", f"/profiles/{profile}/scans", {"modules": ["test.other"]}, status=201
    )
    await api.wait_scan(scan["id"], lambda s: s["status"] == "done")
    assert (await api.json("GET", f"/entities/{page}"))["entity"]["gone_at"] is None


class Other(SourceModule):
    """A source that finds nothing."""

    meta: ClassVar[ModuleMeta] = meta("test.other")

    async def run(self, ctx: ModuleContext, target: Target) -> AsyncIterator[Finding]:
        await ctx.progress(1, 1)
        return
        yield  # pragma: no cover
