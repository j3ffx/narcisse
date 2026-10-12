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
    # A free GitLab personal token: gitlab.com then shows a profile's bio, place and site. Optional.
    gitlab_token: str | None = None
    # Leave out adult sites when looking for accounts.
    exclude_adult: bool = False
    # Fediverse instances to look on, besides the ones the module knows (host names).
    fediverse_instances: tuple[str, ...] = ()

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
        values = {k: v for k, v in data.items() if k in known}
        values["fediverse_instances"] = tuple(
            host for host in values.get("fediverse_instances") or () if isinstance(host, str)
        )
        return cls(**values)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
