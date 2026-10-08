"""SQLite access: many readers, one writer at a time, schema kept up to date by Alembic."""

import asyncio
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TypeVar

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

MIGRATIONS = Path(__file__).parent / "migrations"

T = TypeVar("T")


def _set_pragmas(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    # WAL: readers never wait for the writer. busy_timeout covers the rare overlap with
    # another process (a CLI command while the server runs).
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def migrate(path: Path) -> None:
    """Creates the database if needed and applies every pending migration."""
    path.parent.mkdir(parents=True, exist_ok=True)
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    engine: Engine = create_engine(f"sqlite:///{path}")
    event.listen(engine, "connect", _set_pragmas)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    engine.dispose()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.engine: AsyncEngine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        event.listen(self.engine.sync_engine, "connect", _set_pragmas)
        self._sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        # SQLite takes one writer at a time: writers queue here rather than on SQLite's lock.
        self._write_lock = asyncio.Lock()
        self._pending: set[asyncio.Task[Any]] = set()

    async def shielded(self, operation: Coroutine[Any, Any, T]) -> T:
        """Runs a database operation to its end even if the caller is cancelled (a run being
        cancelled, a browser closing its stream): cancelling SQLite work midway breaks the
        connection it was using."""
        task = asyncio.create_task(operation)
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)
        return await asyncio.shield(task)

    @asynccontextmanager
    async def read(self) -> AsyncIterator[AsyncSession]:
        async with self._sessions() as session:
            yield session

    @asynccontextmanager
    async def write(self) -> AsyncIterator[AsyncSession]:
        """A session whose changes are committed on exit (rolled back on error)."""
        async with self._write_lock, self._sessions() as session, session.begin():
            yield session

    @asynccontextmanager
    async def snapshot(self) -> AsyncIterator[AsyncSession]:
        """A read that no write can interleave with (several queries, one consistent state)."""
        async with self._write_lock, self._sessions() as session:
            yield session

    async def close(self) -> None:
        if self._pending:
            await asyncio.wait(self._pending)
        await self.engine.dispose()
