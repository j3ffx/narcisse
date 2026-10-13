"""Command line.

- `narcisse open`: what the Start menu shortcut runs. Opens Narcisse, starting it first (in the
  notification area) if it isn't running.
- `narcisse tray`: the server in the background, with its icon in the notification area.
- `narcisse serve`: the server in this terminal (development, scripts).
- `narcisse shortcut`: adds Narcisse to the Start menu (Windows).
"""

import os
import socket
import threading
import time
from dataclasses import replace
from typing import Annotated

import httpx
import typer
import uvicorn

from narcisse import __version__, searxng
from narcisse.app import create_app
from narcisse.config import DEFAULT_PORT, FALLBACK_PORT, HOST, Settings
from narcisse.desktop import mode, system
from narcisse.logs import setup_logging
from narcisse.preferences import Preferences
from narcisse.server import Server

app = typer.Typer(
    help="Narcisse : ce qu’Internet sait de toi, et comment le réduire.",
    no_args_is_help=True,
    add_completion=False,
)

Demo = Annotated[bool, typer.Option("--demo", help="Mode démo : propose le module factice.")]
# The desktop commands open the side chosen last (the tray's "Mode démo") unless told which.
Side = Annotated[
    bool | None,
    typer.Option(
        "--demo/--real",
        help="Mode démo, ou tes vraies données (par défaut : le dernier choisi).",
        show_default=False,
    ),
]
Port = Annotated[int | None, typer.Option(help="Port local (80 si possible, sinon 8765).")]


def _can_listen(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, port))
        except OSError:
            return False
        return True


def _narcisse_answers(port: int) -> bool:
    try:
        response = httpx.get(f"http://{HOST}:{port}/api/info", timeout=2)
        return response.json().get("version") is not None
    except (httpx.HTTPError, ValueError, AttributeError):
        return False


def _locate(port: int | None, demo: bool) -> tuple[Settings, bool]:
    """Where Narcisse runs or will run: (settings, whether it already runs there). Port 80 when
    free, so that the address has no port; else 8765. Raises Exit when no port is usable."""
    settings = Settings.from_env(port=port, demo=demo or None)
    explicit = port is not None or "NARCISSE_PORT" in os.environ
    for candidate in [settings.port] if explicit else [DEFAULT_PORT, FALLBACK_PORT]:
        candidate_settings = replace(settings, port=candidate)
        if _narcisse_answers(candidate):
            return candidate_settings, True
        if _can_listen(candidate):
            return candidate_settings, False
    typer.echo(f"Le port {settings.port} est déjà pris. Essaie : narcisse serve --port 8766")
    raise typer.Exit(1)


def _open_when_ready(server: Server, settings: Settings) -> None:
    while not server.started and not server.should_exit:
        time.sleep(0.05)
    if server.started:
        system.open_window(settings.app_url, settings.url)


@app.command()
def serve(
    port: Port = None,
    demo: Demo = False,
    browser: Annotated[
        bool, typer.Option("--browser/--no-browser", help="Ouvrir le navigateur.")
    ] = True,
    verbose: Annotated[bool, typer.Option("--verbose", help="Journal détaillé.")] = False,
) -> None:
    """Lance Narcisse dans ce terminal, sur 127.0.0.1, et l’ouvre."""
    settings, running = _locate(port, demo)
    if running:
        typer.echo(f"Narcisse tourne déjà sur {settings.url}.")
        if browser:
            system.open_window(settings.app_url, settings.url)
        return
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
    mode = " (mode démo)" if settings.demo else ""
    typer.echo(f"Narcisse {__version__} : {settings.url}{mode}")
    typer.echo(f"Données : {settings.data_dir}. Ctrl+C pour arrêter.")
    if browser:
        threading.Thread(target=_open_when_ready, args=(server, settings), daemon=True).start()
    server.run()


@app.command()
def tray(
    port: Port = None,
    demo: Side = None,
    open_window: Annotated[
        bool, typer.Option("--open", help="Ouvrir Narcisse une fois prêt.")
    ] = False,
) -> None:
    """Lance Narcisse en arrière-plan, avec son icône dans la zone de notification."""
    settings, running = _locate(port, mode.demo_remembered() if demo is None else demo)
    if running:
        if open_window:
            system.open_window(settings.app_url, settings.url)
        return
    from narcisse.desktop.native import prepare_native_ui
    from narcisse.desktop.tray import Tray  # pystray needs a desktop session: load it only here

    setup_logging(settings, terminal=False)
    prepare_native_ui()  # before the tray creates its windows
    Tray(settings, open_on_start=open_window).run()


@app.command("open")
def open_(port: Port = None, demo: Side = None) -> None:
    """Ouvre Narcisse, en le démarrant d’abord s’il ne tourne pas."""
    demo = mode.demo_remembered() if demo is None else demo
    settings, running = _locate(port, demo)
    if running:
        system.open_window(settings.app_url, settings.url)
        return
    args = [
        "tray",
        "--open",
        "--demo" if demo else "--real",
        *(["--port", str(port)] if port else []),
    ]
    system.spawn_detached(system.command(*args))


@app.command()
def shortcut(demo: Demo = False) -> None:
    """Ajoute Narcisse au menu Démarrer (Windows) : un clic l’ouvre, en le démarrant si besoin.

    L’entrée ouvre le dernier mode choisi (« Mode démo » dans le menu de l’icône) ; --demo le règle
    sur la démo."""
    if not system.IS_WINDOWS:
        typer.echo(
            "Le raccourci n’existe que sous Windows pour l’instant : lance « narcisse open »."
        )
        raise typer.Exit(1)
    if demo:
        mode.remember(True)
    path = system.create_shortcut(system.command("open"))
    typer.echo(f"Raccourci créé : {path}")
    side = "le mode démo" if mode.demo_remembered() else "tes vraies données"
    typer.echo(f"Il ouvre {side} ; la case « Mode démo » du menu de l’icône change de côté.")
    typer.echo("Tape « Narcisse » dans le menu Démarrer pour l’ouvrir, ou épingle-le.")


@app.command("searxng")
def searxng_(
    start: Annotated[
        bool, typer.Option(help="La lancer avec Docker (sinon, seulement écrire ses fichiers).")
    ] = True,
    port: Annotated[int, typer.Option(help="Port local de l’instance.")] = searxng.PORT,
) -> None:
    """Installe ta propre instance SearXNG (Docker) pour la recherche web, et la règle."""
    folder = searxng.directory()
    searxng.write(folder, port)
    typer.echo(f"Fichiers de SearXNG : {folder}")
    if not start:
        typer.echo("Lance-la avec « docker compose up -d » dans ce dossier.")
        return
    if searxng.docker() is None:
        typer.echo("Docker est introuvable : installe Docker Desktop, puis relance la commande.")
        raise typer.Exit(1)
    typer.echo("Lancement (le premier téléchargement prend une minute ou deux)…")
    started, said = searxng.start(folder)
    if not started:
        typer.echo(f"Docker n’a pas pu la lancer (Docker Desktop est-il démarré ?) :\n{said}")
        raise typer.Exit(1)
    address = searxng.url(port)
    if not searxng.ready(address):
        typer.echo(f"SearXNG ne répond pas encore sur {address} : réessaie dans un moment.")
        raise typer.Exit(1)
    # The source is a real one: the setting goes to the user's own data, not the demo's.
    path = Settings.from_env(demo=False).preferences_path
    replace(Preferences.load(path), searxng_url=address).save(path)
    typer.echo(f"SearXNG tourne sur {address}, et Narcisse s’en sert pour la recherche web.")


@app.command()
def paths() -> None:
    """Affiche où Narcisse range ses données et son journal."""
    settings = Settings.from_env()
    typer.echo(f"Données : {settings.data_dir}")
    typer.echo(f"Base    : {settings.database_path}")
    typer.echo(f"Journal : {settings.log_dir / 'narcisse.log'}")


def main() -> None:
    app()
