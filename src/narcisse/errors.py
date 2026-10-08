"""Errors the UI can explain: a stable code and its parameters, never a stack trace."""

from typing import Any


class AppError(Exception):
    """An error meant for the user. The UI turns `code` (and `params`) into a sentence."""

    def __init__(self, code: str, *, status: int = 400, params: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.params = params or {}


def not_found(what: str) -> AppError:
    return AppError("not_found", status=404, params={"what": what})
