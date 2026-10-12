"""The user's settings for the sources, kept in the data directory (never in the repository)."""

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class Preferences:
    # A free GitHub personal token: 5,000 requests an hour instead of 60. Optional.
    github_token: str | None = None
    # Leave out adult sites when looking for accounts.
    exclude_adult: bool = False

    @classmethod
    def load(cls, path: Path) -> "Preferences":
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError):
            log.warning("unreadable preferences in %s; using the defaults", path)
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
