"""Runtime settings, read from the environment (see `.env.example`)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_data_path

DEFAULT_PORT = 8765
# Only loopback: the server never listens on a network interface.
HOST = "127.0.0.1"


@dataclass(frozen=True, kw_only=True)
class Settings:
    data_dir: Path
    port: int = DEFAULT_PORT
    # Demo mode shows the fake module and nothing else changes.
    demo: bool = False
    # Speeds up every wait of the engine and the modules (tests and e2e run fake scans faster).
    speed: float = 1.0
    # Origins allowed to change state besides the server's own (the Vite dev server).
    extra_origins: tuple[str, ...] = field(default=())

    @property
    def database_path(self) -> Path:
        return self.data_dir / "narcisse.sqlite3"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def own_origins(self) -> frozenset[str]:
        return frozenset(
            {
                f"http://{HOST}:{self.port}",
                f"http://localhost:{self.port}",
                *self.extra_origins,
            }
        )

    @classmethod
    def from_env(cls, *, port: int | None = None, demo: bool | None = None) -> "Settings":
        env = os.environ
        data_dir = env.get("NARCISSE_DATA_DIR")
        return cls(
            data_dir=Path(data_dir) if data_dir else user_data_path("narcisse", appauthor=False),
            port=port if port is not None else int(env.get("NARCISSE_PORT", DEFAULT_PORT)),
            demo=demo if demo is not None else env.get("NARCISSE_DEMO") == "1",
            speed=float(env.get("NARCISSE_SPEED", "1")),
            extra_origins=tuple(o for o in env.get("NARCISSE_DEV_ORIGINS", "").split(",") if o),
        )
