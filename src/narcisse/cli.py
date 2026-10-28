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
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import httpx
import typer
import uvicorn

from narcisse import __version__, searxng
from narcisse.app import create_app
from narcisse.config import DEFAULT_PORT, FALLBACK_PORT, HOST, Settings
from narcisse.desktop import mode, system, taskbar
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
SCAN_POLL_SECONDS = 5.0

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


def _open(settings: Settings) -> None:
    """Opens the window, and waits for it to get its place on the taskbar before this process
    ends."""
    branding = system.open_window(settings.app_url, settings.url)
    if branding is not None:
        branding.join(taskbar.WAIT_SECONDS)


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
            _open(settings)
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
            _open(settings)
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
        _open(settings)
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


@app.command()
def scan(
    profile: Annotated[
        int | None,
        typer.Option("--profil", help="Le numéro du profil (sinon : les scans programmés dus)."),
    ] = None,
    demo: Side = None,
) -> None:
    """Lance un scan et attend sa fin : celui d’un profil, ou ceux que les profils programment
    (pour cron ou le Planificateur de tâches). Démarre Narcisse s’il ne tourne pas."""
    from narcisse.desktop.state import changes_text

    side = mode.demo_remembered() if demo is None else demo
    settings, running = _locate(None, side)
    if not running:
        system.spawn_detached(system.command("tray", "--demo" if side else "--real"))
        deadline = time.monotonic() + 60
        while not _narcisse_answers(settings.port):
            if time.monotonic() > deadline:
                typer.echo("Narcisse n’a pas démarré : regarde son journal (narcisse paths).")
                raise typer.Exit(1)
            time.sleep(1)
    api = f"http://{HOST}:{settings.port}/api"
    with httpx.Client(timeout=30) as client:
        path = f"/profiles/{profile}/scans" if profile is not None else "/schedule/due"
        started = client.post(f"{api}{path}", json={})
        if started.status_code >= 400:
            typer.echo(f"Scan refusé ({started.json().get('code', started.status_code)}).")
            raise typer.Exit(1)
        detail = started.json()
        if detail is None:
            typer.echo("Aucun scan programmé n’est dû pour l’instant.")
            return
        typer.echo(f"Scan de « {detail['profile_name']} » lancé…")
        while detail["status"] in ("running", "paused"):
            time.sleep(SCAN_POLL_SECONDS)
            detail = client.get(f"{api}/scans/{detail['id']}").json()
    changes = changes_text((detail.get("notes") or {}).get("changes"))
    typer.echo(f"Scan terminé : {changes or str(detail['results_count']) + ' résultat(s).'}")


@app.command()
def backup(
    out: Annotated[
        Path | None, typer.Option("--out", help="Fichier ou dossier où l’écrire.")
    ] = None,
    encrypt: Annotated[
        bool,
        typer.Option(
            "--chiffrer", help="La chiffrer avec une phrase de passe (et garder les tokens)."
        ),
    ] = False,
    demo: Demo = False,
) -> None:
    """Sauvegarde toutes les données de Narcisse dans un fichier .narcisse."""
    from narcisse.storage import backup as backups

    settings = Settings.from_env(demo=demo or None)
    if not settings.database_path.exists():
        typer.echo("Rien à sauvegarder : Narcisse n’a encore aucune donnée ici.")
        raise typer.Exit(1)
    passphrase = None
    if encrypt:
        passphrase = typer.prompt("Phrase de passe", hide_input=True, confirmation_prompt=True)
    now = datetime.now(UTC)
    target = out or Path.cwd()
    if target.is_dir():
        target = target / backups.file_name(now, encrypted=bool(passphrase))
    target.write_bytes(backups.create(settings, now, passphrase))
    typer.echo(f"Sauvegarde écrite : {target}")
    if passphrase:
        typer.echo("Sans la phrase de passe, personne ne pourra la relire, pas même Narcisse.")


@app.command()
def restore(
    file: Annotated[Path, typer.Argument(help="La sauvegarde .narcisse à restaurer.")],
    demo: Demo = False,
) -> None:
    """Remplace toutes les données de Narcisse par celles d’une sauvegarde (Narcisse arrêté)."""
    from narcisse.errors import AppError
    from narcisse.storage import backup as backups
    from narcisse.storage.database import migrate

    settings, running = _locate(None, demo)
    if running:
        typer.echo(
            "Narcisse tourne : quitte-le d’abord (menu de l’icône), ou restaure depuis ses "
            "Réglages."
        )
        raise typer.Exit(1)
    data = file.read_bytes()
    passphrase = None
    if backups.is_sealed(data):
        passphrase = typer.prompt("Phrase de passe", hide_input=True)
    try:
        restored = backups.read(data, passphrase)
    except AppError as exc:
        typer.echo(f"Impossible de restaurer cette sauvegarde ({exc.code}).")
        raise typer.Exit(1) from exc
    now = datetime.now(UTC)
    if settings.database_path.exists():
        safety = backups.safety_path(settings, now)
        safety.write_bytes(backups.create(settings, now))
        typer.echo(f"Tes données d’avant sont gardées dans : {safety}")
    backups.replace_data(settings, restored)
    migrate(settings.database_path)
    typer.echo(
        f"Restauré : {restored.manifest.profiles} profil(s), sauvegarde du "
        f"{restored.manifest.created_at[:10]}."
    )


def main() -> None:
    app()
