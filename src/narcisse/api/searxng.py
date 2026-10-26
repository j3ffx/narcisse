"""The user's own SearXNG, installed and started from the app on their click (`searxng.py`)."""

from fastapi import APIRouter

from narcisse import searxng
from narcisse.api.deps import ServicesDep
from narcisse.errors import AppError
from narcisse.preferences import Preferences
from narcisse.schemas import SearxngOut

router = APIRouter(tags=["searxng"])


async def _status(s: ServicesDep) -> SearxngOut:
    address = Preferences.load(s.settings.preferences_path).searxng_url
    launch = s.searxng.current
    return SearxngOut(
        docker=searxng.docker() is not None,
        address=address,
        running=await s.searxng.answers(address or searxng.url()),
        state=launch.state,
        step=launch.step,
        error=launch.error,
    )


@router.get("/searxng")
async def get_searxng(s: ServicesDep) -> SearxngOut:
    return await _status(s)


@router.post("/searxng/start", status_code=202)
async def start_searxng(s: ServicesDep) -> SearxngOut:
    """Installs the instance if needed and starts it (opening Docker Desktop if it isn't
    running); the UI follows the launch through GET /searxng."""
    if s.settings.demo:
        # Demo mode never reaches real sources, nor starts anything on the machine.
        raise AppError("searxng_demo", status=409)
    s.searxng.start()
    return await _status(s)
