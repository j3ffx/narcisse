"""Alembic environment: migrations run on the connection `storage.database.migrate` passes."""

from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext

from narcisse.storage.models import Base, UTCDateTime


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    # Migrations must not import the models: they describe the schema as it was.
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime()"
    return False


connection = context.config.attributes["connection"]
context.configure(
    connection=connection,
    target_metadata=Base.metadata,
    # SQLite can't alter most column properties: let Alembic copy and swap tables instead.
    render_as_batch=True,
    render_item=render_item,
)
with context.begin_transaction():
    context.run_migrations()
