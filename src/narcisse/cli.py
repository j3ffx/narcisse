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
from narcisse.i18n import Lang, resolve, system_lang
from narcisse.logs import setup_logging
from narcisse.preferences import Preferences
from narcisse.server import Server


def lang() -> Lang:
    """The language chosen in the settings, else the system's."""
    try:
        return resolve(Preferences.load(Settings.from_env().preferences_path).ui_lang)
    except (OSError, ValueError):
        return system_lang()


def say(fr: str, en: str) -> str:
    return en if lang() == "en" else fr


app = typer.Typer(
    help=say(
        "Narcisse : ce qu’Internet sait de toi, et comment le réduire.",
        "Narcisse: what the Internet knows about you, and how to shrink it.",
    ),
    no_args_is_help=True,
    add_completion=False,
)

Demo = Annotated[
    bool,
    typer.Option(
        "--demo",
        help=say("Mode démo : propose le module factice.", "Demo mode: offers the fake module."),
    ),
]
# The desktop commands open the side chosen last (the tray's "Mode démo") unless told which.
Side = Annotated[
    bool | None,
    typer.Option(
        "--demo/--real",
        help=say(
            "Mode démo, ou tes vraies données (par défaut : le dernier choisi).",
            "Demo mode, or your own data (by default: the one chosen last).",
        ),
        show_default=False,
    ),
]
SCAN_POLL_SECONDS = 5.0

Port = Annotated[
    int | None,
    typer.Option(
        help=say(
            "Port local (80 si possible, sinon 8765).", "Local port (80 if possible, else 8765)."
        )
    ),
]


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
    typer.echo(
        say(
            f"Le port {settings.port} est déjà pris. Essaie : narcisse serve --port 8766",
            f"Port {settings.port} is taken. Try: narcisse serve --port 8766",
        )
    )
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


@app.command(
    help=say(
        "Lance Narcisse dans ce terminal, sur 127.0.0.1, et l’ouvre.",
        "Runs Narcisse in this terminal, on 127.0.0.1, and opens it.",
    )
)
def serve(
    port: Port = None,
    demo: Demo = False,
    browser: Annotated[
        bool,
        typer.Option(
            "--browser/--no-browser", help=say("Ouvrir le navigateur.", "Open the browser.")
        ),
    ] = True,
    verbose: Annotated[
        bool, typer.Option("--verbose", help=say("Journal détaillé.", "Detailed log."))
    ] = False,
) -> None:
    settings, running = _locate(port, demo)
    if running:
        typer.echo(
            say(
                f"Narcisse tourne déjà sur {settings.url}.",
                f"Narcisse already runs on {settings.url}.",
            )
        )
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
    side = say(" (mode démo)", " (demo mode)") if settings.demo else ""
    typer.echo(f"Narcisse {__version__} : {settings.url}{side}")
    typer.echo(
        say(
            f"Données : {settings.data_dir}. Ctrl+C pour arrêter.",
            f"Data: {settings.data_dir}. Ctrl+C to stop.",
        )
    )
    if browser:
        threading.Thread(target=_open_when_ready, args=(server, settings), daemon=True).start()
    server.run()


@app.command(
    help=say(
        "Lance Narcisse en arrière-plan, avec son icône dans la zone de notification.",
        "Runs Narcisse in the background, with its icon in the notification area.",
    )
)
def tray(
    port: Port = None,
    demo: Side = None,
    open_window: Annotated[
        bool,
        typer.Option(
            "--open", help=say("Ouvrir Narcisse une fois prêt.", "Open Narcisse once ready.")
        ),
    ] = False,
) -> None:
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


@app.command(
    "open",
    help=say(
        "Ouvre Narcisse, en le démarrant d’abord s’il ne tourne pas.",
        "Opens Narcisse, starting it first if it isn't running.",
    ),
)
def open_(port: Port = None, demo: Side = None) -> None:
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


@app.command(
    help=say(
        "Ajoute Narcisse au menu Démarrer (Windows) : un clic l’ouvre, en le démarrant si besoin. "
        "L’entrée ouvre le dernier mode choisi (« Mode démo » dans le menu de l’icône) ; --demo "
        "le règle sur la démo.",
        "Adds Narcisse to the Start menu (Windows): a click opens it, starting it if need be. "
        "The entry opens the side chosen last (“Demo mode” in the icon's menu); --demo sets it "
        "to the demo.",
    )
)
def shortcut(demo: Demo = False) -> None:
    if not system.IS_WINDOWS:
        typer.echo(
            say(
                "Le raccourci n’existe que sous Windows pour l’instant : lance « narcisse open ».",
                "The shortcut only exists on Windows for now: run “narcisse open”.",
            )
        )
        raise typer.Exit(1)
    if demo:
        mode.remember(True)
    path = system.create_shortcut(system.command("open"))
    typer.echo(say(f"Raccourci créé : {path}", f"Shortcut made: {path}"))
    demo_side = mode.demo_remembered()
    typer.echo(
        say(
            f"Il ouvre {'le mode démo' if demo_side else 'tes vraies données'} ; la case "
            "« Mode démo » du menu de l’icône change de côté.",
            f"It opens {'the demo' if demo_side else 'your own data'}; the “Demo mode” box of "
            "the icon's menu switches sides.",
        )
    )
    typer.echo(
        say(
            "Tape « Narcisse » dans le menu Démarrer pour l’ouvrir, ou épingle-le.",
            "Type “Narcisse” in the Start menu to open it, or pin it.",
        )
    )


@app.command(
    "searxng",
    help=say(
        "Installe ta propre instance SearXNG (Docker) pour la recherche web, et la règle.",
        "Installs your own SearXNG instance (Docker) for the web search, and sets it.",
    ),
)
def searxng_(
    start: Annotated[
        bool,
        typer.Option(
            help=say(
                "La lancer avec Docker (sinon, seulement écrire ses fichiers).",
                "Start it with Docker (else, only write its files).",
            )
        ),
    ] = True,
    port: Annotated[
        int, typer.Option(help=say("Port local de l’instance.", "The instance's local port."))
    ] = searxng.PORT,
) -> None:
    folder = searxng.directory()
    searxng.write(folder, port)
    typer.echo(say(f"Fichiers de SearXNG : {folder}", f"SearXNG's files: {folder}"))
    if not start:
        typer.echo(
            say(
                "Lance-la avec « docker compose up -d » dans ce dossier.",
                "Start it with “docker compose up -d” in this folder.",
            )
        )
        return
    if searxng.docker() is None:
        typer.echo(
            say(
                "Docker est introuvable : installe Docker Desktop, puis relance la commande.",
                "Docker can't be found: install Docker Desktop, then run the command again.",
            )
        )
        raise typer.Exit(1)
    typer.echo(
        say(
            "Lancement (le premier téléchargement prend une minute ou deux)…",
            "Starting (the first download takes a minute or two)…",
        )
    )
    started, said = searxng.start(folder)
    if not started:
        typer.echo(
            say(
                f"Docker n’a pas pu la lancer (Docker Desktop est-il démarré ?) :\n{said}",
                f"Docker couldn't start it (is Docker Desktop running?):\n{said}",
            )
        )
        raise typer.Exit(1)
    address = searxng.url(port)
    if not searxng.ready(address):
        typer.echo(
            say(
                f"SearXNG ne répond pas encore sur {address} : réessaie dans un moment.",
                f"SearXNG doesn't answer on {address} yet: try again in a moment.",
            )
        )
        raise typer.Exit(1)
    # The source is a real one: the setting goes to the user's own data, not the demo's.
    path = Settings.from_env(demo=False).preferences_path
    replace(Preferences.load(path), searxng_url=address).save(path)
    typer.echo(
        say(
            f"SearXNG tourne sur {address}, et Narcisse s’en sert pour la recherche web.",
            f"SearXNG runs on {address}, and Narcisse uses it for the web search.",
        )
    )


@app.command(
    help=say(
        "Affiche où Narcisse range ses données et son journal.",
        "Shows where Narcisse keeps its data and its log.",
    )
)
def paths() -> None:
    settings = Settings.from_env()
    typer.echo(say(f"Données : {settings.data_dir}", f"Data:     {settings.data_dir}"))
    typer.echo(say(f"Base    : {settings.database_path}", f"Database: {settings.database_path}"))
    log = settings.log_dir / "narcisse.log"
    typer.echo(say(f"Journal : {log}", f"Log:      {log}"))


@app.command(
    help=say(
        "Lance un scan et attend sa fin : celui d’un profil, ou ceux que les profils programment "
        "(pour cron ou le Planificateur de tâches). Démarre Narcisse s’il ne tourne pas.",
        "Starts a scan and waits for its end: a profile's, or the ones the profiles schedule "
        "(for cron or the Task Scheduler). Starts Narcisse if it isn't running.",
    )
)
def scan(
    profile: Annotated[
        int | None,
        typer.Option(
            "--profil",
            "--profile",
            help=say(
                "Le numéro du profil (sinon : les scans programmés dus).",
                "The profile's number (else: the scheduled scans due).",
            ),
        ),
    ] = None,
    demo: Side = None,
) -> None:
    from narcisse.desktop.state import changes_text

    side = mode.demo_remembered() if demo is None else demo
    settings, running = _locate(None, side)
    if not running:
        system.spawn_detached(system.command("tray", "--demo" if side else "--real"))
        deadline = time.monotonic() + 60
        while not _narcisse_answers(settings.port):
            if time.monotonic() > deadline:
                typer.echo(
                    say(
                        "Narcisse n’a pas démarré : regarde son journal (narcisse paths).",
                        "Narcisse didn't start: look at its log (narcisse paths).",
                    )
                )
                raise typer.Exit(1)
            time.sleep(1)
    api = f"http://{HOST}:{settings.port}/api"
    with httpx.Client(timeout=30) as client:
        path = f"/profiles/{profile}/scans" if profile is not None else "/schedule/due"
        started = client.post(f"{api}{path}", json={})
        if started.status_code >= 400:
            code = started.json().get("code", started.status_code)
            typer.echo(say(f"Scan refusé ({code}).", f"Scan refused ({code})."))
            raise typer.Exit(1)
        detail = started.json()
        if detail is None:
            typer.echo(
                say(
                    "Aucun scan programmé n’est dû pour l’instant.", "No scheduled scan is due yet."
                )
            )
            return
        name = detail["profile_name"]
        typer.echo(say(f"Scan de « {name} » lancé…", f"Scan of “{name}” started…"))
        while detail["status"] in ("running", "paused"):
            time.sleep(SCAN_POLL_SECONDS)
            detail = client.get(f"{api}/scans/{detail['id']}").json()
    changes = changes_text((detail.get("notes") or {}).get("changes"), lang())
    count = detail["results_count"]
    typer.echo(
        say(
            f"Scan terminé : {changes or f'{count} résultat(s).'}",
            f"Scan finished: {changes or f'{count} result(s).'}",
        )
    )


@app.command(
    help=say(
        "Sauvegarde toutes les données de Narcisse dans un fichier .narcisse.",
        "Backs up all of Narcisse's data into a .narcisse file.",
    )
)
def backup(
    out: Annotated[
        Path | None,
        typer.Option(
            "--out", help=say("Fichier ou dossier où l’écrire.", "File or folder to write it to.")
        ),
    ] = None,
    encrypt: Annotated[
        bool,
        typer.Option(
            "--chiffrer",
            "--encrypt",
            help=say(
                "La chiffrer avec une phrase de passe (et garder les tokens).",
                "Encrypt it with a passphrase (and keep the tokens).",
            ),
        ),
    ] = False,
    demo: Demo = False,
) -> None:
    from narcisse.storage import backup as backups

    settings = Settings.from_env(demo=demo or None)
    if not settings.database_path.exists():
        typer.echo(
            say(
                "Rien à sauvegarder : Narcisse n’a encore aucune donnée ici.",
                "Nothing to back up: Narcisse has no data here yet.",
            )
        )
        raise typer.Exit(1)
    passphrase = None
    if encrypt:
        passphrase = typer.prompt(
            say("Phrase de passe", "Passphrase"), hide_input=True, confirmation_prompt=True
        )
    now = datetime.now(UTC)
    target = out or Path.cwd()
    if target.is_dir():
        target = target / backups.file_name(now, encrypted=bool(passphrase))
    target.write_bytes(backups.create(settings, now, passphrase))
    typer.echo(say(f"Sauvegarde écrite : {target}", f"Backup written: {target}"))
    if passphrase:
        typer.echo(
            say(
                "Sans la phrase de passe, personne ne pourra la relire, pas même Narcisse.",
                "Without the passphrase, no one can read it back, not even Narcisse.",
            )
        )


@app.command(
    help=say(
        "Remplace toutes les données de Narcisse par celles d’une sauvegarde (Narcisse arrêté).",
        "Replaces all of Narcisse's data with a backup's (Narcisse stopped).",
    )
)
def restore(
    file: Annotated[
        Path,
        typer.Argument(
            help=say("La sauvegarde .narcisse à restaurer.", "The .narcisse backup to restore.")
        ),
    ],
    demo: Demo = False,
) -> None:
    from narcisse.errors import AppError
    from narcisse.storage import backup as backups
    from narcisse.storage.database import migrate

    settings, running = _locate(None, demo)
    if running:
        typer.echo(
            say(
                "Narcisse tourne : quitte-le d’abord (menu de l’icône), ou restaure depuis ses "
                "Réglages.",
                "Narcisse is running: quit it first (icon menu), or restore from its Settings.",
            )
        )
        raise typer.Exit(1)
    data = file.read_bytes()
    passphrase = None
    if backups.is_sealed(data):
        passphrase = typer.prompt(say("Phrase de passe", "Passphrase"), hide_input=True)
    try:
        restored = backups.read(data, passphrase)
    except AppError as exc:
        typer.echo(
            say(
                f"Impossible de restaurer cette sauvegarde ({exc.code}).",
                f"This backup can't be restored ({exc.code}).",
            )
        )
        raise typer.Exit(1) from exc
    now = datetime.now(UTC)
    if settings.database_path.exists():
        safety = backups.safety_path(settings, now)
        safety.write_bytes(backups.create(settings, now))
        typer.echo(
            say(
                f"Tes données d’avant sont gardées dans : {safety}",
                f"Your data from before is kept in: {safety}",
            )
        )
    backups.replace_data(settings, restored)
    migrate(settings.database_path)
    profiles, day = restored.manifest.profiles, restored.manifest.created_at[:10]
    typer.echo(
        say(
            f"Restauré : {profiles} profil(s), sauvegarde du {day}.",
            f"Restored: {profiles} profile(s), backup of {day}.",
        )
    )


def main() -> None:
    app()
