"""The FastAPI application: API under /api, the built UI everywhere else."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.telemetry import TelemetryConfig

from narcisse import __version__
from narcisse.api import profiles, scans
from narcisse.api.deps import Services, ServicesDep
from narcisse.clock import Clock
from narcisse.config import Settings
from narcisse.engine.engine import Engine
from narcisse.engine.events import EventBus
from narcisse.engine.http import new_transport_client
from narcisse.engine.plugin import SourceModule
from narcisse.errors import AppError
from narcisse.modules import discover
from narcisse.schemas import AppInfo
from narcisse.security import LocalOnlyMiddleware
from narcisse.storage.database import Database, migrate

log = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "web" / "static"
# FastAPI can export traces to an OpenTelemetry collector named by OTEL_* variables: never here.
NO_TELEMETRY: TelemetryConfig = {
    "tracing": False,
    "metrics": False,
    "logs": False,
    "operation_spans": False,
    "auto_configure": False,
}
UI_MISSING = """<!doctype html><html lang="fr"><meta charset="utf-8"><title>Narcisse</title>
<body style="font-family:system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem">
<h1>Narcisse</h1><p>L’API tourne, mais l’interface n’a pas été construite.</p>
<p>Depuis le dossier du projet : <code>npm ci &amp;&amp; npm run build</code>, puis relance
<code>narcisse serve</code>. Pour développer : <code>npm run dev</code>.</p></body></html>"""


def app_from_env() -> FastAPI:
    """For `uvicorn --factory` (development with reload): settings from the environment."""
    from narcisse.logs import setup_logging

    settings = Settings.from_env()
    setup_logging(settings)
    return create_app(settings)


def create_app(
    settings: Settings,
    *,
    modules: dict[str, SourceModule] | None = None,
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """`modules` and `http_transport` let tests swap the sources and the network."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await asyncio.to_thread(migrate, settings.database_path)
        db = Database(settings.database_path)
        bus = EventBus(db, Clock(settings.speed))
        await bus.start()
        available = discover() if modules is None else modules
        offered = {n: m for n, m in available.items() if settings.demo or not m.meta.demo}
        async with new_transport_client(transport=http_transport) as client:
            engine = Engine(bus, offered, client)
            await engine.start()
            app.state.services = Services(settings, db, bus, engine)
            log.info("Narcisse %s ready, data in %s", __version__, settings.data_dir)
            try:
                yield
            finally:
                bus.close()
                await engine.stop()
                await db.close()

    app = FastAPI(
        title="Narcisse",
        version=__version__,
        lifespan=lifespan,
        telemetry=NO_TELEMETRY,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.add_middleware(LocalOnlyMiddleware, allowed_origins=settings.own_origins)

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse({"code": exc.code, "params": exc.params}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()})
        return JSONResponse(
            {"code": "invalid_request", "params": {"fields": fields}}, status_code=422
        )

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unexpected error on %s %s", request.method, request.url.path)
        return JSONResponse({"code": "internal_error", "params": {}}, status_code=500)

    api = APIRouter(prefix="/api")

    @api.get("/info", tags=["meta"])
    async def info(s: ServicesDep) -> AppInfo:
        return AppInfo(version=__version__, demo=s.settings.demo, data_dir=str(s.settings.data_dir))

    api.include_router(profiles.router)
    api.include_router(scans.router)

    @api.api_route(
        "/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"], include_in_schema=False
    )
    async def unknown_api(path: str) -> Response:
        raise AppError("not_found", status=404, params={"what": "route"})

    app.include_router(api)

    @app.get("/{path:path}", include_in_schema=False)
    async def ui(path: str) -> Response:
        if not (STATIC / "index.html").is_file():
            return HTMLResponse(UI_MISSING)
        file = (STATIC / path).resolve()
        if path and file.is_file() and file.is_relative_to(STATIC.resolve()):
            immutable = path.startswith("assets/")
            cache = "public, max-age=31536000, immutable" if immutable else "no-cache"
            return FileResponse(file, headers={"Cache-Control": cache})
        # Client-side routes all get the app shell.
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    return app
