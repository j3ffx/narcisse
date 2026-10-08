"""Command line: `narcisse serve` starts everything; more commands come with scans from scripts."""

import os
import socket
import threading
import time
import webbrowser
from dataclasses import replace
from typing import Annotated

import httpx
import typer
import uvicorn

from narcisse import __version__
from narcisse.app import create_app
from narcisse.config import DEFAULT_PORT, FALLBACK_PORT, HOST, Settings
from narcisse.logs import setup_logging
from narcisse.server import Server

app = typer.Typer(
    help="Narcisse : ce qu’Internet sait de toi, et comment le réduire.",
    no_args_is_help=True,
    add_completion=False,
)


def _can_listen(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, port))
        except OSError:
            return False
        return True


def _narcisse_answers(url: str) -> bool:
    try:
        return httpx.get(f"{url}/api/info", timeout=2).json().get("version") is not None
    except (httpx.HTTPError, ValueError, AttributeError):
        return False


def _open_when_ready(server: Server, url: str) -> None:
    while not server.started and not server.should_exit:
        time.sleep(0.05)
    if server.started:
        webbrowser.open(url)


@app.command()
def serve(
    port: Annotated[
        int | None, typer.Option(help="Port local (80 si possible, sinon 8765).")
    ] = None,
    demo: Annotated[
        bool, typer.Option("--demo", help="Mode démo : propose le module factice.")
    ] = False,
    browser: Annotated[
        bool, typer.Option("--browser/--no-browser", help="Ouvrir le navigateur.")
    ] = True,
    verbose: Annotated[bool, typer.Option("--verbose", help="Journal détaillé.")] = False,
) -> None:
    """Lance Narcisse sur 127.0.0.1 et ouvre l’interface dans le navigateur."""
    settings = Settings.from_env(port=port, demo=demo or None)
    explicit = port is not None or "NARCISSE_PORT" in os.environ
    for candidate in [settings.port] if explicit else [DEFAULT_PORT, FALLBACK_PORT]:
        candidate_settings = replace(settings, port=candidate)
        if _narcisse_answers(f"http://{HOST}:{candidate}"):
            typer.echo(f"Narcisse tourne déjà sur {candidate_settings.url}.")
            if browser:
                webbrowser.open(candidate_settings.url)
            return
        if _can_listen(candidate):
            settings = candidate_settings
            break
    else:
        typer.echo(f"Le port {settings.port} est déjà pris. Essaie : narcisse serve --port 8766")
        raise typer.Exit(1)
    url = settings.url
    setup_logging(settings, verbose=verbose)
    config = uvicorn.Config(
        create_app(settings),
        host=HOST,
        port=settings.port,
        log_config=None,
        access_log=False,
        timeout_graceful_shutdown=3,
    )
    server = Server(config)
    typer.echo(f"Narcisse {__version__} : {url}" + (" (mode démo)" if settings.demo else ""))
    typer.echo(f"Données : {settings.data_dir}. Ctrl+C pour arrêter.")
    if browser:
        threading.Thread(target=_open_when_ready, args=(server, url), daemon=True).start()
    server.run()


@app.command()
def paths() -> None:
    """Affiche où Narcisse range ses données et son journal."""
    settings = Settings.from_env()
    typer.echo(f"Données : {settings.data_dir}")
    typer.echo(f"Base    : {settings.database_path}")
    typer.echo(f"Journal : {settings.log_dir / 'narcisse.log'}")


def main() -> None:
    app()
