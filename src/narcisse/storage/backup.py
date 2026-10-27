"""Backups of all of Narcisse's data, and restoring one.

A backup is a zip: `manifest.json` (what it is, from which version, how many profiles), a
consistent copy of the database (SQLite's online backup), and the settings. The free tokens
(GitHub, GitLab) are only kept when the backup is encrypted. Encrypted, the whole zip is sealed
with a key derived from the user's passphrase (scrypt, then AES-GCM): without the passphrase,
nothing can be read, Narcisse included.
"""

import io
import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from narcisse import __version__
from narcisse.config import Settings
from narcisse.errors import AppError
from narcisse.preferences import Preferences
from narcisse.storage.database import MIGRATIONS

FORMAT = "narcisse-backup"
VERSION = 1
SEALED = b"NARCISSE-SEALED-1"  # what an encrypted backup starts with
SCRYPT = {"n": 2**15, "r": 8, "p": 1}  # about 32 MB and a fraction of a second
DATABASE = "narcisse.sqlite3"
SETTINGS = "preferences.json"
MANIFEST = "manifest.json"
TOKENS = ("github_token", "gitlab_token")


@dataclass(frozen=True)
class Manifest:
    format: str
    version: int
    narcisse: str
    revision: str  # the database schema's migration
    created_at: str
    profiles: int
    encrypted: bool
    tokens: bool  # whether the settings kept the tokens


@dataclass(frozen=True)
class Backup:
    manifest: Manifest
    database: bytes
    preferences: dict[str, Any]


def head_revision() -> str:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    return head


def _key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, **SCRYPT).derive(passphrase.encode("utf-8"))


def seal(data: bytes, passphrase: str) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(12)
    return SEALED + salt + nonce + AESGCM(_key(passphrase, salt)).encrypt(nonce, data, SEALED)


def unseal(data: bytes, passphrase: str) -> bytes:
    body = data[len(SEALED) :]
    salt, nonce, sealed = body[:16], body[16:28], body[28:]
    try:
        return AESGCM(_key(passphrase, salt)).decrypt(nonce, sealed, SEALED)
    except InvalidTag as exc:
        raise AppError("backup_wrong_passphrase", status=422) from exc


def _copy_database(source: Path, target: Path) -> tuple[str, int]:
    """A consistent copy while the server may write; returns its revision and profile count."""
    # closing(): a connection's own `with` only commits, and Windows can't delete an open file.
    with closing(sqlite3.connect(source)) as live, closing(sqlite3.connect(target)) as copy:
        live.backup(copy)
        revision = copy.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        profiles = copy.execute("SELECT count(*) FROM profile").fetchone()[0]
    return str(revision), int(profiles)


def create(settings: Settings, now: datetime, passphrase: str | None = None) -> bytes:
    """The backup of everything, sealed with the passphrase if one is given."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / DATABASE
        revision, profiles = _copy_database(settings.database_path, copy)
        preferences = Preferences.load(settings.preferences_path)
        if not passphrase:
            preferences = replace(preferences, github_token=None, gitlab_token=None)
        manifest = Manifest(
            format=FORMAT,
            version=VERSION,
            narcisse=__version__,
            revision=revision,
            created_at=now.isoformat(),
            profiles=profiles,
            encrypted=bool(passphrase),
            tokens=bool(passphrase),
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST, json.dumps(asdict(manifest), indent=2))
            archive.write(copy, DATABASE)
            archive.writestr(SETTINGS, json.dumps(asdict(preferences), indent=2))
    data = buffer.getvalue()
    return seal(data, passphrase) if passphrase else data


def is_sealed(data: bytes) -> bool:
    return data.startswith(SEALED)


def read(data: bytes, passphrase: str | None = None) -> Backup:
    """Opens a backup and checks it can be restored here: a Narcisse backup, whole, from a
    schema this version knows."""
    if is_sealed(data):
        if not passphrase:
            raise AppError("backup_passphrase_needed", status=422)
        data = unseal(data, passphrase)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = Manifest(**json.loads(archive.read(MANIFEST)))
            database = archive.read(DATABASE)
            preferences = json.loads(archive.read(SETTINGS))
    except (zipfile.BadZipFile, KeyError, TypeError, ValueError) as exc:
        raise AppError("backup_invalid", status=422) from exc
    if manifest.format != FORMAT or manifest.version > VERSION:
        raise AppError("backup_invalid", status=422)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / DATABASE
        path.write_bytes(database)
        try:
            with closing(sqlite3.connect(path)) as db:
                ok = db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                revision = db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise AppError("backup_invalid", status=422) from exc
    if not ok:
        raise AppError("backup_invalid", status=422)
    if not _known(str(revision)):
        # Made by a later Narcisse: its schema can't be read by this one.
        raise AppError("backup_too_new", status=422, params={"version": manifest.narcisse})
    return Backup(manifest=manifest, database=database, preferences=preferences)


def _known(revision: str) -> bool:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    try:
        return ScriptDirectory.from_config(config).get_revision(revision) is not None
    except CommandError:
        return False


def replace_data(settings: Settings, backup: Backup) -> None:
    """Puts the backup's database and settings in place (Narcisse's database must be closed).
    Tokens the backup doesn't carry are kept from the current settings."""
    database = settings.database_path
    for suffix in ("-wal", "-shm"):
        Path(f"{database}{suffix}").unlink(missing_ok=True)
    staged = database.with_name(database.name + ".restoring")
    staged.write_bytes(backup.database)
    os.replace(staged, database)
    current = Preferences.load(settings.preferences_path)
    restored = Preferences.load_dict(backup.preferences)
    if not backup.manifest.tokens:
        restored = replace(
            restored, github_token=current.github_token, gitlab_token=current.gitlab_token
        )
    restored.save(settings.preferences_path)


def safety_path(settings: Settings, now: datetime) -> Path:
    """Where the state before a restore is kept, in case the restore wasn't what the user
    meant."""
    folder = settings.data_dir / "sauvegardes"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"avant-restauration-{now:%Y-%m-%d-%H%M%S}.narcisse"


def file_name(now: datetime, encrypted: bool) -> str:
    return f"narcisse-{now:%Y-%m-%d}{'-chiffree' if encrypted else ''}.narcisse"
