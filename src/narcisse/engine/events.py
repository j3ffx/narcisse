"""Events: stored with the change they describe, then announced to whoever is listening.

The database is the only source: a listener is just told "there is something after id N" and reads
it. A slow or reconnecting browser therefore never misses or reorders anything.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from narcisse.clock import Clock
from narcisse.storage.database import Database
from narcisse.storage.models import Event

# A browser closed longer than that starts again from a fresh snapshot.
KEEP_EVENTS = timedelta(days=7)


@dataclass
class Transaction:
    session: AsyncSession
    clock: Clock
    _events: list[Event] = field(default_factory=list)

    def emit(self, type_: str, payload: BaseModel | dict[str, Any], scan_id: int | None) -> None:
        data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        event = Event(type=type_, scan_id=scan_id, payload=data, created_at=self.clock.now())
        self.session.add(event)
        self._events.append(event)


class EventBus:
    def __init__(self, db: Database, clock: Clock) -> None:
        self.db = db
        self.clock = clock
        self.latest_id = 0
        self._changed = asyncio.Event()
        self.closed = False

    async def start(self) -> None:
        async with self.db.write() as session:
            await session.execute(
                delete(Event).where(Event.created_at < self.clock.now() - KEEP_EVENTS)
            )
        async with self.db.read() as session:
            self.latest_id = (await session.scalar(select(func.max(Event.id)))) or 0

    def close(self) -> None:
        """Ends the streams (server shutdown)."""
        self.closed = True
        self._notify()

    def _notify(self) -> None:
        changed, self._changed = self._changed, asyncio.Event()
        changed.set()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Transaction]:
        """A write whose events are announced once it is committed."""
        async with self.db.write() as session:
            tx = Transaction(session, self.clock)
            yield tx
            await session.flush()
        if tx._events:
            self.latest_id = max(self.latest_id, *(e.id for e in tx._events))
            self._notify()

    async def wait_after(self, event_id: int) -> bool:
        """Waits until an event newer than `event_id` exists; False once the bus is closed."""
        while self.latest_id <= event_id and not self.closed:
            await self._changed.wait()
        return not self.closed

    async def read_after(self, event_id: int, limit: int = 500) -> list[Event]:
        return await self.db.shielded(self._read_after(event_id, limit))

    async def _read_after(self, event_id: int, limit: int) -> list[Event]:
        async with self.db.read() as session:
            rows = await session.scalars(
                select(Event).where(Event.id > event_id).order_by(Event.id).limit(limit)
            )
            return list(rows)

    async def oldest_id(self) -> int | None:
        return await self.db.shielded(self._oldest_id())

    async def _oldest_id(self) -> int | None:
        async with self.db.read() as session:
            return await session.scalar(select(func.min(Event.id)))
