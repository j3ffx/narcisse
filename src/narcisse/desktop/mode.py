"""Which side the desktop app opens on: the user's own data, or the demo.

Each mode keeps its data in its own directory, so the choice is kept apart from both (in the
user's configuration directory): the Start menu entry and the start with Windows open the side
chosen last, and the tray menu switches it.
"""

import json
import logging
import os
from pathlib import Path

from platformdirs import user_config_path

log = logging.getLogger(__name__)


def mode_path() -> Path:
    base = os.environ.get("NARCISSE_CONFIG_DIR")
    return (Path(base) if base else user_config_path("narcisse", appauthor=False)) / "mode.json"


def demo_remembered() -> bool:
    """Whether the demo was chosen last (the user's own data when nothing was chosen)."""
    try:
        data = json.loads(mode_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        log.warning("unreadable mode choice in %s; opening the user's own data", mode_path())
        return False
    return isinstance(data, dict) and data.get("demo") is True


def remember(demo: bool) -> None:
    path = mode_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"demo": demo}), encoding="utf-8")
