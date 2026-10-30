"""Backing up all of Narcisse's data and restoring it: plain and encrypted, from the settings page
and from the command line."""

import base64
import io
import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from narcisse import cli
from narcisse.config import Settings
from narcisse.preferences import Preferences
from narcisse.storage import backup
from tests.conftest import Api, ApiFactory
from tests.fakes import Steps

TOKEN = "ab" * 20  # low entropy: not a secret to gitleaks
KEY = "cd" * 20


async def make(api: Api, passphrase: str | None = None) -> bytes:
    response = await api.client.post("/api/backup", json={"passphrase": passphrase})
    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].startswith("attachment;")
    return response.content


async def restore(api: Api, data: bytes, passphrase: str | None = None, status: int = 200) -> Any:
    body = {"data": base64.b64encode(data).decode(), "passphrase": passphrase}
    return await api.json("POST", "/restore", body, status=status)


async def profile_names(api: Api) -> list[str]:
    return [p["name"] for p in await api.json("GET", "/profiles")]


def manifest(data: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        result: dict[str, Any] = json.loads(archive.read("manifest.json"))
        return result


async def test_a_backup_brings_everything_back(api: Api, settings: Settings) -> None:
    await api.profile(("name", "Jeanne Exemple"), name="Jeanne Exemple")
    await api.json(
        "PATCH", "/preferences", {"github_token": TOKEN, "llm_key": KEY, "exclude_adult": True}
    )
    data = await make(api)
    assert manifest(data)["profiles"] == 1
    assert manifest(data)["tokens"] is False
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        saved = archive.read("preferences.json").decode()
        assert TOKEN not in saved
        assert KEY not in saved

    # Things change after the backup…
    await api.profile(name="Autre profil")
    await api.json("PATCH", "/preferences", {"exclude_adult": False})

    restored = await restore(api, data)

    assert restored["profiles"] == 1
    assert restored["safety"].endswith(".narcisse")  # the data before the restore, kept
    assert await profile_names(api) == ["Jeanne Exemple"]
    preferences = await api.json("GET", "/preferences")
    assert preferences["exclude_adult"] is True
    # A plain backup carries no token: the current one stays.
    assert preferences["github_token_set"] is True
    assert preferences["llm_key_set"] is True
    # Narcisse runs on, on the restored data.
    profile = await api.profile(("username", "jeanne"), name="Après")
    scan = await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    await api.wait_scan(scan["id"], lambda s: s["status"] == "done")


async def test_an_encrypted_backup_needs_its_passphrase(api: Api) -> None:
    await api.json("PATCH", "/preferences", {"github_token": TOKEN})
    data = await make(api, "une phrase de passe")
    assert backup.is_sealed(data)
    assert b"preferences.json" not in data  # nothing readable without the passphrase
    await api.json("PATCH", "/preferences", {"github_token": ""})

    needed = await restore(api, data, status=422)
    assert needed["code"] == "backup_passphrase_needed"
    wrong = await restore(api, data, "pas la bonne", status=422)
    assert wrong["code"] == "backup_wrong_passphrase"
    await restore(api, data, "une phrase de passe")
    # Encrypted, the backup kept the token.
    assert (await api.json("GET", "/preferences"))["github_token_set"] is True


async def test_what_is_not_a_backup_is_refused(api: Api, tmp_path: Path) -> None:
    error = await restore(api, b"not a zip", status=422)
    assert error["code"] == "backup_invalid"
    bad = await api.json("POST", "/restore", {"data": "%%%"}, status=422)
    assert bad["code"] == "backup_invalid"

    # Made by a later Narcisse: a schema this one doesn't know.
    data = await make(api)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        database = tmp_path / "db.sqlite3"
        database.write_bytes(archive.read("narcisse.sqlite3"))
        files = {n: archive.read(n) for n in archive.namelist()}
    with closing(sqlite3.connect(database)) as db:
        db.execute("UPDATE alembic_version SET version_num = '9999'")
        db.commit()
    files["narcisse.sqlite3"] = database.read_bytes()
    later = io.BytesIO()
    with zipfile.ZipFile(later, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    error = await restore(api, later.getvalue(), status=422)
    assert error["code"] == "backup_too_new"


async def test_no_restore_while_a_scan_runs(make_api: ApiFactory) -> None:
    api = await make_api({"test.steps": Steps(steps=50, delay=5)})
    data = await make(api)
    profile = await api.profile(("username", "jeanne"))
    await api.json("POST", f"/profiles/{profile}/scans", {}, status=201)
    error = await restore(api, data, status=409)
    assert error["code"] == "restore_while_scanning"


def test_the_command_line_backs_up_and_restores(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NARCISSE_DATA_DIR", str(settings.data_dir))
    monkeypatch.setattr(cli, "_locate", lambda port, demo: (settings, False))
    runner = CliRunner()
    nothing = runner.invoke(cli.app, ["backup", "--out", str(tmp_path)])
    assert nothing.exit_code == 1

    from narcisse.storage.database import migrate

    migrate(settings.database_path)
    Preferences(exclude_adult=True).save(settings.preferences_path)
    made = runner.invoke(cli.app, ["backup", "--out", str(tmp_path)])
    assert made.exit_code == 0, made.output
    [file] = list(tmp_path.glob("*.narcisse"))

    Preferences().save(settings.preferences_path)
    restored = runner.invoke(cli.app, ["restore", str(file)])
    assert restored.exit_code == 0, restored.output
    assert Preferences.load(settings.preferences_path).exclude_adult is True
    assert list((settings.data_dir / "sauvegardes").glob("avant-restauration-*.narcisse"))

    sealed = runner.invoke(
        cli.app,
        ["backup", "--out", str(tmp_path / "sealed"), "--chiffrer"],
        input="phrase\nphrase\n",
    )
    assert sealed.exit_code == 0, sealed.output
    assert backup.is_sealed((tmp_path / "sealed").read_bytes())
