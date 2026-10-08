"""What every route needs, taken from the running application."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from narcisse.config import Settings
from narcisse.engine.engine import Engine
from narcisse.engine.events import EventBus
from narcisse.storage.database import Database


@dataclass(frozen=True)
class Services:
    settings: Settings
    db: Database
    bus: EventBus
    engine: Engine


def _services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDep = Annotated[Services, Depends(_services)]
