"""Narcisse in French and in English: which language it speaks, the proofs written in it, and
the sources, the icon, the command line and the assistant that follow it."""

import pytest
from typer.testing import CliRunner

from narcisse import cli, notes
from narcisse.desktop.state import changes_text, reminder_notice, summarize
from narcisse.i18n import accepted, pick, resolve
from narcisse.modules import discover
from tests.conftest import Api, ApiFactory


@pytest.mark.parametrize(
    ("header", "lang"),
    [
        ("fr-FR,fr;q=0.9,en;q=0.8", "fr"),
        ("en-GB,en;q=0.9", "en"),
        ("de-DE,en;q=0.5,fr;q=0.8", "fr"),  # by preference, not by order
        ("de-DE", None),
        (None, None),
    ],
)
def test_the_browsers_language_is_read_by_preference(header: str | None, lang: str | None) -> None:
    assert accepted(header) == lang


def test_the_users_choice_wins_then_the_browser_then_the_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NARCISSE_LANG", "en")
    assert resolve("fr", "en-GB") == "fr"
    assert resolve("auto", "fr-FR") == "fr"
    assert resolve("auto", None) == "en"
    assert pick({"fr": "Bonjour", "en": "Hello"}, "en") == "Hello"
    assert pick("Même texte", "en") == "Même texte"


def test_every_note_says_something_in_both_languages() -> None:
    for code, texts in notes.NOTES.items():
        assert set(texts) == {"fr", "en"}, code


def test_a_note_reads_in_each_language_with_its_place() -> None:
    said = notes.note("link_given", where=notes.note("in_github_bio", login="jeanne-exemple"))
    assert (
        notes.render(said, "fr") == "Lien indiqué dans la bio du profil GitHub « jeanne-exemple »."
    )
    assert notes.render(said, "en") == (
        "Link given in the bio of the GitHub profile “jeanne-exemple”."
    )
    # Text read on a page follows the note, in its own language.
    assert notes.text(said, "Bio : Jeanne", "en") == (
        "Link given in the bio of the GitHub profile “jeanne-exemple”. Bio : Jeanne"
    )
    # A proof stored before notes existed keeps its sentence.
    assert notes.text(None, "Ancienne phrase.", "en") == "Ancienne phrase."
    assert notes.render({"code": "unknown"}, "fr") is None
    with pytest.raises(KeyError):
        notes.note("no-such-note")


def test_french_elides_before_a_vowel() -> None:
    said = notes.note("dmarc_reports", domain="adobe.com")
    assert notes.render(said, "fr") == "Adresse qui reçoit les rapports DMARC d’adobe.com."


def test_every_source_has_its_title_and_description_in_both_languages() -> None:
    for name, module in discover().items():
        for text in (module.meta.title, module.meta.description):
            assert isinstance(text, dict), name
            assert text.get("fr"), name
            assert text.get("en"), name


async def demo_scan(api: Api) -> int:
    profile = await api.profile(("name", "Jeanne Exemple"))
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    await api.wait_scan(scan["id"], lambda s: s["status"] == "done")
    return int(scan["id"])


async def test_the_api_writes_proofs_and_sources_in_the_language_asked(api: Api) -> None:
    scan_id = await demo_scan(api)
    english = {"Accept-Language": "en-GB,en;q=0.9"}

    french = (await api.json("GET", f"/scans/{scan_id}/results"))["items"][0]["excerpt"]
    response = await api.client.get(f"/api/scans/{scan_id}/results", headers=english)
    assert french.startswith("Résultat fictif du module de démonstration")
    assert response.json()["items"][0]["excerpt"].startswith("Fictitious result of the demo module")

    modules = (await api.client.get("/api/modules", headers=english)).json()
    assert modules[0]["title"] == "Demo module"

    # The user's choice wins over the browser's.
    await api.json("PATCH", "/preferences", {"ui_lang": "fr"})
    response = await api.client.get(f"/api/scans/{scan_id}/results", headers=english)
    assert response.json()["items"][0]["excerpt"].startswith("Résultat fictif")
    assert (await api.json("GET", "/preferences"))["ui_lang"] == "fr"


async def test_live_results_follow_the_chosen_language(make_api: ApiFactory) -> None:
    api = await make_api()
    await api.json("PATCH", "/preferences", {"ui_lang": "en"})
    await demo_scan(api)
    events = await api.app.state.services.bus.read_after(0, limit=10_000)
    results = [e for e in events if e.type == "result.created"]
    assert results[0].payload["excerpt"].startswith("Fictitious result")


async def test_the_assistant_is_asked_and_answers_in_the_language(api: Api) -> None:
    scan_id = await demo_scan(api)
    trace = (await api.json("GET", f"/scans/{scan_id}/results"))["items"][0]["entity"]["id"]
    await api.json("PATCH", "/preferences", {"llm_provider": "demo", "ui_lang": "en"})
    text = (await api.json("GET", f"/entities/{trace}/prompt?task=triage"))["text"]
    assert text.startswith("What the person declared:")
    assert "Fictitious result" in text
    asked = await api.json("POST", f"/entities/{trace}/annotations", {"task": "triage"}, 202)
    assert asked["prompt"].startswith("What the person declared:")


def test_the_tray_speaks_english() -> None:
    assert summarize(None, "en").tooltip == "Narcisse: starting…"
    assert changes_text({"new": 2, "gone": 1, "modified": 0}, "en") == "2 new traces, 1 gone."
    assert (reminder_notice(1, "en") or "").startswith("A request has waited a month")


def test_the_command_line_speaks_the_chosen_language(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    monkeypatch.setenv("NARCISSE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NARCISSE_LANG", "en")
    result = CliRunner().invoke(cli.app, ["paths"])
    assert result.exit_code == 0
    assert result.output.startswith("Data:")
    monkeypatch.setenv("NARCISSE_LANG", "fr")
    assert CliRunner().invoke(cli.app, ["paths"]).output.startswith("Données :")
