"""What every route needs, taken from the running application."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from narcisse.config import Settings
from narcisse.engine.engine import Engine
from narcisse.engine.events import EventBus
from narcisse.i18n import Lang, resolve
from narcisse.llm.assistant import Assistant
from narcisse.llm.local import Puller
from narcisse.preferences import Preferences
from narcisse.searxng import Launcher
from narcisse.storage.database import Database


@dataclass(frozen=True)
class Services:
    settings: Settings
    db: Database
    bus: EventBus
    engine: Engine
    searxng: Launcher
    assistant: Assistant
    pull: Puller
    # Closes the database, runs a function (that replaces its files), opens it again: a restore.
    reopen: Callable[[Callable[[], None]], Awaitable[None]]


def _services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDep = Annotated[Services, Depends(_services)]


def _lang(request: Request) -> Lang:
    """The language of this answer: the user's choice, else the browser's."""
    services: Services = request.app.state.services
    preferences = Preferences.load(services.settings.preferences_path)
    return resolve(preferences.ui_lang, request.headers.get("accept-language"))


LangDep = Annotated[Lang, Depends(_lang)]
