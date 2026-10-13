"""Migrations that rewrite data, from a database as an older version left it."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from narcisse.storage.database import MIGRATIONS, migrate

NOW = "2026-10-13 12:00:00"


def at_revision(path: Path, revision: str) -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)
    engine.dispose()


def test_phone_numbers_already_stored_are_written_one_way(tmp_path: Path) -> None:
    path = tmp_path / "narcisse.sqlite3"
    at_revision(path, "0004")
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO profile (id, name, kind, settings, created_at, updated_at) "
                "VALUES (1, 'Jeanne Exemple', 'personal', '{}', :now, :now)"
            ),
            {"now": NOW},
        )
        for i, (value, normalized) in enumerate(
            [("06 39 98 00 00", "0639980000"), ("+33 1 99 00 12 34", "+33199001234")], 1
        ):
            db.execute(
                text(
                    "INSERT INTO seed (id, profile_id, kind, value, normalized, status, "
                    "created_at) VALUES (:id, 1, 'phone', :value, :normalized, 'watch', :now)"
                ),
                {"id": i, "value": value, "normalized": normalized, "now": NOW},
            )
        # Two traces of one number: the second can't take the form the first takes.
        for i, normalized in enumerate(["0199001234", "+33199001234", "0639980000"], 1):
            db.execute(
                text(
                    "INSERT INTO entity (id, profile_id, kind, normalized, display, status, "
                    "attributes, first_seen, last_seen) VALUES (:id, 1, 'phone', :normalized, "
                    ":normalized, 'unreviewed', '{}', :now, :now)"
                ),
                {"id": i, "normalized": normalized, "now": NOW},
            )
    engine.dispose()

    migrate(path)

    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as db:
        seeds = db.execute(text("SELECT normalized FROM seed ORDER BY id")).scalars().all()
        entities = db.execute(text("SELECT normalized FROM entity ORDER BY id")).scalars().all()
    engine.dispose()
    assert seeds == ["+33639980000", "+33199001234"]
    assert entities == ["0199001234", "+33199001234", "+33639980000"]
