"""The desktop side: tray state and notifications, Windows integration (never the real registry,
never a real window), the launch commands."""

import sys
import types
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from narcisse import cli
from narcisse.config import Settings
from narcisse.desktop import mode, system, taskbar
from narcisse.desktop.art import TrayState, tray_icon
from narcisse.desktop.state import notifications, reminder_notice, summarize


def run(id_: int, status: str, kind: str = "name") -> dict[str, Any]:
    return {"id": id_, "status": status, "input_kind": kind, "input_value": "Jeanne Exemple"}


def scan(id_: int, status: str, *runs: dict[str, Any], results: int = 0) -> dict[str, Any]:
    return {
        "id": id_,
        "status": status,
        "profile_name": "Jeanne Exemple",
        "results_count": results,
        "runs": list(runs),
    }


def activity(*scans: dict[str, Any]) -> dict[str, Any]:
    return {"last_event_id": 1, "scans": list(scans)}


# What the tray shows


def test_the_tray_says_what_goes_on() -> None:
    assert summarize(None).tooltip == "Narcisse : démarrage…"
    idle = summarize(activity(scan(1, "done", run(1, "done"))))
    assert (idle.state, idle.tooltip) == (TrayState.IDLE, "Narcisse : rien en cours")
    busy = summarize(activity(scan(1, "running", run(1, "running")), scan(2, "running")))
    assert (busy.state, busy.tooltip) == (TrayState.RUNNING, "Narcisse : 2 scans en cours")
    assert busy.running_scans == (1, 2)
    paused = summarize(activity(scan(1, "paused", run(1, "paused"))))
    assert (paused.state, paused.tooltip) == (TrayState.PAUSED, "Narcisse : 1 scan en pause")
    failing = summarize(activity(scan(1, "running", run(1, "running"), run(2, "failed"))))
    assert failing.state == TrayState.FAILED
    assert failing.tooltip == "Narcisse : 1 scan en cours, 1 recherche en erreur"


def test_notifications_tell_of_ends_and_failures_once() -> None:
    before = activity(scan(1, "running", run(1, "running"), run(2, "running", "username")))
    failed = activity(scan(1, "running", run(1, "running"), run(2, "failed", "username")))
    done = activity(scan(1, "done", run(1, "done"), run(2, "failed", "username"), results=48))

    assert notifications(None, before) == []  # nothing when the tray starts
    [failure] = notifications(before, failed)
    assert failure.title == "Une recherche est en erreur"
    assert "Pseudo « Jeanne Exemple »" in failure.message
    [end] = notifications(failed, done)  # the failure is not told twice
    assert (end.title, end.message) == ("Scan terminé : Jeanne Exemple", "48 résultats.")


def test_the_icon_changes_with_the_state() -> None:
    icons = {state: tray_icon(state, 32).tobytes() for state in TrayState}
    assert len(set(icons.values())) == len(TrayState)


# Windows integration


class FakeRegistry(types.ModuleType):
    """Stands for `winreg`: tests never write the real registry."""

    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        super().__init__("winreg")
        self.values: dict[str, str] = {}

    def OpenKey(self, *_: Any) -> "FakeRegistry":
        return self

    def __enter__(self) -> "FakeRegistry":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def QueryValueEx(self, _key: Any, name: str) -> tuple[str, int]:
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], 1

    def SetValueEx(self, _key: Any, name: str, _r: int, _t: int, value: str) -> None:
        self.values[name] = value

    def DeleteValue(self, _key: Any, name: str) -> None:
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> FakeRegistry:
    fake = FakeRegistry()
    monkeypatch.setitem(sys.modules, "winreg", fake)
    monkeypatch.setattr(system, "AUTOSTART_SUPPORTED", True)
    return fake


def test_start_with_windows_is_off_until_ticked(registry: FakeRegistry) -> None:
    assert not system.autostart_enabled()
    system.set_autostart(True, [r"C:\Program Files\Python\pythonw.exe", "-m", "narcisse", "tray"])
    assert system.autostart_enabled()
    assert registry.values["Narcisse"] == (
        r'"C:\Program Files\Python\pythonw.exe" -m narcisse tray'
    )
    system.set_autostart(False, [])
    system.set_autostart(False, [])  # unticking twice is harmless
    assert not system.autostart_enabled()


def test_commands_run_without_a_console_window(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "python.exe").touch()
    (tmp_path / "pythonw.exe").touch()
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr(system, "IS_WINDOWS", True)
    assert system.command("open") == [str(tmp_path / "pythonw.exe"), "-m", "narcisse", "open"]


def test_narcisse_opens_in_an_app_window_when_the_browser_can(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launched: list[Any] = []
    branded: list[str] = []
    monkeypatch.setattr("subprocess.Popen", lambda args, **_: launched.append(args))
    monkeypatch.setattr("webbrowser.open", lambda url: launched.append(url))
    monkeypatch.setattr(taskbar, "brand_new_windows", lambda command, icon: branded.append(command))

    monkeypatch.setattr(system, "_app_mode_browser", lambda: "chrome.exe")
    system.open_window("http://narcisse.localhost", "http://narcisse")
    monkeypatch.setattr(system, "_app_mode_browser", lambda: None)
    system.open_window("http://narcisse.localhost", "http://narcisse")

    assert launched == [
        ["chrome.exe", "--app=http://narcisse.localhost/?fenetre=1"],
        "http://narcisse",
    ]
    # Only the app window gets Narcisse's place on the taskbar: pinned, it runs `narcisse open`.
    [command] = branded
    assert command.endswith("-m narcisse open")


def test_the_shortcut_script_never_contains_the_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> None:
        seen["script"] = args[-1]
        seen["env"] = kwargs["env"]

    monkeypatch.setattr(system, "IS_WINDOWS", True)
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(taskbar, "brand_shortcut", lambda path: True)  # never the real entry
    target = r"D:\Outils de Jeanne O'Exemple\pythonw.exe"
    path = system.create_shortcut([target, "-m", "narcisse", "open", "--demo"])

    assert path.name == "Narcisse.lnk"
    assert target not in seen["script"]
    assert seen["env"]["NARCISSE_TARGET"] == target
    assert seen["env"]["NARCISSE_ARGS"] == "-m narcisse open --demo"


# Launching


def test_the_app_window_always_uses_the_secure_address(tmp_path: Path) -> None:
    short = Settings(data_dir=tmp_path, short_host=True)
    assert (short.url, short.app_url) == ("http://narcisse", "http://narcisse.localhost")
    other = Settings(data_dir=tmp_path, port=8765)
    assert other.app_url == "http://narcisse.localhost:8765"


def test_open_starts_narcisse_only_when_it_is_not_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(system, "open_window", lambda app, tab: calls.append(("open", app)))
    monkeypatch.setattr(system, "spawn_detached", lambda args: calls.append(("spawn", args[-3:])))
    settings = Settings(data_dir=tmp_path)

    monkeypatch.setattr(cli, "_locate", lambda port, demo: (settings, True))
    assert CliRunner().invoke(cli.app, ["open"]).exit_code == 0
    monkeypatch.setattr(cli, "_locate", lambda port, demo: (settings, False))
    assert CliRunner().invoke(cli.app, ["open", "--demo"]).exit_code == 0

    assert calls == [
        ("open", "http://narcisse.localhost"),
        ("spawn", ["tray", "--open", "--demo"]),
    ]


def test_open_starts_the_side_chosen_last(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    started: list[list[str]] = []
    asked: list[bool] = []
    monkeypatch.setattr(system, "spawn_detached", lambda args: started.append(args[-2:]))

    def locate(port: int | None, demo: bool) -> tuple[Settings, bool]:
        asked.append(demo)
        return Settings(data_dir=tmp_path), False

    monkeypatch.setattr(cli, "_locate", locate)
    assert mode.demo_remembered() is False  # nothing chosen yet: the user's own data
    CliRunner().invoke(cli.app, ["open"])
    mode.remember(True)
    CliRunner().invoke(cli.app, ["open"])
    CliRunner().invoke(cli.app, ["open", "--real"])  # said explicitly: that side, once

    assert asked == [False, True, False]
    assert started == [["--open", "--real"], ["--open", "--demo"], ["--open", "--real"]]
    assert mode.demo_remembered() is True


def test_an_unreadable_choice_opens_the_users_own_data() -> None:
    mode.mode_path().parent.mkdir(parents=True)
    mode.mode_path().write_text("{not json", encoding="utf-8")
    assert mode.demo_remembered() is False


def test_the_shortcut_opens_the_side_chosen_last(monkeypatch: pytest.MonkeyPatch) -> None:
    made: list[list[str]] = []
    monkeypatch.setattr(system, "IS_WINDOWS", True)

    def create_shortcut(args: list[str]) -> Path:
        made.append(args)
        return Path("Narcisse.lnk")

    monkeypatch.setattr(system, "create_shortcut", create_shortcut)

    result = CliRunner().invoke(cli.app, ["shortcut", "--demo"])

    assert result.exit_code == 0, result.output
    assert made[0][-2:] == ["narcisse", "open"]  # no side written in: the one chosen last
    assert mode.demo_remembered() is True
    assert "mode démo" in result.output


def test_the_native_menu_setup_does_nothing_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    from narcisse.desktop import native

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("ctypes.WinDLL", None, raising=False)  # would fail if reached
    native.prepare_native_ui()


def test_the_daily_word_on_requests_to_remind() -> None:
    assert reminder_notice(0) is None
    assert reminder_notice(1) == (
        "Une demande attend sa réponse depuis un mois : prépare sa relance dans « À faire »."
    )
    assert reminder_notice(3).startswith("3 demandes attendent")  # type: ignore[union-attr]
