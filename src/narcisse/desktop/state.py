"""What the tray says, from the activity the API reports. Pure, so that it is easy to test."""

from dataclasses import dataclass
from typing import Any

from narcisse.desktop.art import TrayState
from narcisse.i18n import Lang

ACTIVE = ("running", "paused")
KIND_LABELS = {
    "fr": {
        "name": "Nom",
        "username": "Pseudo",
        "email": "Email",
        "phone": "Téléphone",
        "address": "Adresse",
        "domain": "Domaine",
        "organization": "Organisation",
        "account": "Compte",
    },
    "en": {
        "name": "Name",
        "username": "Username",
        "email": "Email",
        "phone": "Phone",
        "address": "Address",
        "domain": "Domain",
        "organization": "Organization",
        "account": "Account",
    },
}
# The tray's menu, in both languages.
MENU = {
    "fr": {
        "open": "Ouvrir Narcisse",
        "pause": "Mettre en pause les scans en cours",
        "notifications": "Notifications",
        "demo": "Mode démo",
        "autostart": "Démarrer avec Windows",
        "restart": "Redémarrer",
        "quit": "Quitter",
        "stopped": "Narcisse s’est arrêté. Le détail est dans son journal.",
    },
    "en": {
        "open": "Open Narcisse",
        "pause": "Pause the running scans",
        "notifications": "Notifications",
        "demo": "Demo mode",
        "autostart": "Start with Windows",
        "restart": "Restart",
        "quit": "Quit",
        "stopped": "Narcisse stopped. The details are in its log.",
    },
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


def summarize(activity: dict[str, Any] | None, lang: Lang = "fr") -> Summary:
    """The tray's colour and tooltip. `None`: the server does not answer (yet)."""
    fr = lang == "fr"
    if activity is None:
        return Summary(TrayState.IDLE, "Narcisse : démarrage…" if fr else "Narcisse: starting…", ())
    scans = activity["scans"]
    running = tuple(s["id"] for s in scans if s["status"] == "running")
    paused = [s for s in scans if s["status"] == "paused"]
    failed = [
        r for s in scans if s["status"] in ACTIVE for r in s["runs"] if r["status"] == "failed"
    ]
    if running:
        state = TrayState.FAILED if failed else TrayState.RUNNING
        count = _plural(len(running), "scan")
        text = f"Narcisse : {count} en cours" if fr else f"Narcisse: {count} running"
    elif paused:
        state = TrayState.PAUSED
        count = _plural(len(paused), "scan")
        text = f"Narcisse : {count} en pause" if fr else f"Narcisse: {count} paused"
    else:
        state = TrayState.IDLE
        text = "Narcisse : rien en cours" if fr else "Narcisse: nothing running"
    if failed:
        word = "recherche" if fr else "search"
        errors = _plural(len(failed), word).replace("searchs", "searches")
        text += f", {errors} en erreur" if fr else f", {errors} failed"
    # Windows cuts tray tooltips at 127 characters.
    return Summary(state, text[:127], running)


def changes_text(changes: dict[str, int] | None, lang: Lang = "fr") -> str | None:
    """« 3 nouvelles traces, 1 disparue » (what a scan found new since the previous one)."""
    if changes is None:
        return None
    new, gone, modified = (changes.get(k, 0) for k in ("new", "gone", "modified"))
    if not (new or gone or modified):
        return (
            "Rien de nouveau depuis le scan précédent."
            if lang == "fr"
            else "Nothing new since the previous scan."
        )
    parts = []
    if lang == "fr":
        if new:
            parts.append(f"{new} nouvelle{'s' if new > 1 else ''} trace{'s' if new > 1 else ''}")
        if gone:
            parts.append(f"{gone} disparue{'s' if gone > 1 else ''}")
        if modified:
            parts.append(f"{modified} modifiée{'s' if modified > 1 else ''}")
    else:
        if new:
            parts.append(f"{new} new trace{'s' if new > 1 else ''}")
        if gone:
            parts.append(f"{gone} gone")
        if modified:
            parts.append(f"{modified} changed")
    return ", ".join(parts).capitalize() + "."


def notifications(
    before: dict[str, Any] | None, after: dict[str, Any] | None, lang: Lang = "fr"
) -> list[Notification]:
    """What changed between two looks at the activity that deserves a notification: a scan that
    finished, a search that failed. Nothing on the first look (no flood when the tray starts)."""
    if before is None or after is None:
        return []
    fr = lang == "fr"
    old_scans = {s["id"]: s for s in before["scans"]}
    old_runs = {r["id"]: r for s in before["scans"] for r in s["runs"]}
    found: list[Notification] = []
    for scan in after["scans"]:
        old = old_scans.get(scan["id"])
        if old is not None and old["status"] in ACTIVE and scan["status"] == "done":
            results = _plural(scan["results_count"], "résultat" if fr else "result")
            found.append(
                Notification(
                    f"Scan terminé : {scan['profile_name']}"
                    if fr
                    else f"Scan finished: {scan['profile_name']}",
                    changes_text((scan.get("notes") or {}).get("changes"), lang) or f"{results}.",
                )
            )
        for run in scan["runs"]:
            previous = old_runs.get(run["id"])
            if run["status"] == "failed" and (previous is None or previous["status"] != "failed"):
                kind = KIND_LABELS[lang].get(run["input_kind"], run["input_kind"])
                found.append(
                    Notification(
                        "Une recherche est en erreur" if fr else "A search failed",
                        f"{scan['profile_name']} · {kind} « {run['input_value']} ». "
                        "Ouvre Narcisse pour la relancer."
                        if fr
                        else f"{scan['profile_name']} · {kind} “{run['input_value']}”. "
                        "Open Narcisse to retry it.",
                    )
                )
    return found


def reminder_notice(count: int, lang: Lang = "fr") -> str | None:
    """The tray's daily word on the requests a month old without an answer."""
    if count <= 0:
        return None
    if lang == "en":
        if count == 1:
            return "A request has waited a month for its answer: prepare its reminder in “To do”."
        return (
            f"{count} requests have waited a month for their answer: prepare their reminders in "
            "“To do”."
        )
    if count == 1:
        return "Une demande attend sa réponse depuis un mois : prépare sa relance dans « À faire »."
    return (
        f"{count} demandes attendent leur réponse depuis un mois : prépare leur relance dans "
        "« À faire »."
    )
