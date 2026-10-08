"""Writes a migration for the changes made to `storage/models.py`.

uv run python scripts/new-migration.py "add the remediation table"
"""

import sys
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from narcisse.storage.database import MIGRATIONS, migrate

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "schema.sqlite3"
    migrate(path)  # the schema as the existing migrations leave it
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        n = len(list((MIGRATIONS / "versions").glob("*.py")))
        command.revision(config, message=sys.argv[1], autogenerate=True, rev_id=f"{n + 1:04d}")
    engine.dispose()
