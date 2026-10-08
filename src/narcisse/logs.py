"""Logs go to a rotating file in the data directory (stack traces included) and, briefly, to the
terminal. The UI never shows them."""

import logging
from logging.handlers import RotatingFileHandler

from narcisse.config import Settings

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(settings: Settings, *, verbose: bool = False) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    file = RotatingFileHandler(
        settings.log_dir / "narcisse.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file.setFormatter(logging.Formatter(FORMAT))
    file.setLevel(logging.DEBUG if verbose else logging.INFO)
    terminal = logging.StreamHandler()
    terminal.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    terminal.setLevel(logging.INFO if verbose else logging.WARNING)
    root = logging.getLogger()
    root.handlers = [file, terminal]
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    # Request lines and HTTP client chatter are noise at INFO.
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
