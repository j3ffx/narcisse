"""What the tray says, from the activity the API reports. Pure, so that it is easy to test."""

from dataclasses import dataclass
from typing import Any

from narcisse.desktop.art import TrayState

ACTIVE = ("running", "paused")
KIND_LABELS = {
    "name": "Nom",
    "username": "Pseudo",
    "email": "Email",
    "phone": "Téléphone",
    "address": "Adresse",
    "domain": "Domaine",
    "organization": "Organisation",
    "account": "Compte",
}


@dataclass(frozen=True)
class Summary:
    state: TrayState
    tooltip: str
    running_scans: tuple[int, ...]  # ids of the scans a "pause all" would pause


@dataclass(frozen=True)
class Notification:
    title: str
    message: str


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'s' if count > 1 else ''}"


def summarize(activity: dict[str, Any] | None) -> Summary:
    """The tray's colour and tooltip. `None`: the server does not answer (yet)."""
    if activity is None:
        return Summary(TrayState.IDLE, "Narcisse : démarrage…", ())
    scans = activity["scans"]
    running = tuple(s["id"] for s in scans if s["status"] == "running")
    paused = [s for s in scans if s["status"] == "paused"]
    failed = [
        r for s in scans if s["status"] in ACTIVE for r in s["runs"] if r["status"] == "failed"
    ]
    if running:
        state = TrayState.FAILED if failed else TrayState.RUNNING
        text = f"Narcisse : {_plural(len(running), 'scan')} en cours"
    elif paused:
        state = TrayState.PAUSED
        text = f"Narcisse : {_plural(len(paused), 'scan')} en pause"
    else:
        state = TrayState.IDLE
        text = "Narcisse : rien en cours"
    if failed:
        text += f", {_plural(len(failed), 'recherche')} en erreur"
    # Windows cuts tray tooltips at 127 characters.
    return Summary(state, text[:127], running)


def notifications(
    before: dict[str, Any] | None, after: dict[str, Any] | None
) -> list[Notification]:
    """What changed between two looks at the activity that deserves a notification: a scan that
    finished, a search that failed. Nothing on the first look (no flood when the tray starts)."""
    if before is None or after is None:
        return []
    old_scans = {s["id"]: s for s in before["scans"]}
    old_runs = {r["id"]: r for s in before["scans"] for r in s["runs"]}
    found: list[Notification] = []
    for scan in after["scans"]:
        old = old_scans.get(scan["id"])
        if old is not None and old["status"] in ACTIVE and scan["status"] == "done":
            found.append(
                Notification(
                    f"Scan terminé : {scan['profile_name']}",
                    f"{_plural(scan['results_count'], 'résultat')}.",
                )
            )
        for run in scan["runs"]:
            previous = old_runs.get(run["id"])
            if run["status"] == "failed" and (previous is None or previous["status"] != "failed"):
                kind = KIND_LABELS.get(run["input_kind"], run["input_kind"])
                found.append(
                    Notification(
                        "Une recherche est en erreur",
                        f"{scan['profile_name']} · {kind} « {run['input_value']} ». "
                        "Ouvre Narcisse pour la relancer.",
                    )
                )
    return found


def reminder_notice(count: int) -> str | None:
    """The tray's daily word on the requests a month old without an answer."""
    if count <= 0:
        return None
    if count == 1:
        return "Une demande attend sa réponse depuis un mois : prépare sa relance dans « À faire »."
    return (
        f"{count} demandes attendent leur réponse depuis un mois : prépare leur relance dans "
        "« À faire »."
    )
