"""The user's Claude Code, run headless (`claude -p`): their own subscription, nothing to set up
in Narcisse but the choice.

Each question is a fresh process with no tools, no saved session, none of the user's settings,
hooks, MCP servers or CLAUDE.md (`--safe-mode`), in an empty folder: it can only read the text it
is given and answer in the JSON shape asked (`--json-schema`). What it sends goes to Anthropic,
so it counts as remote. Checked against Claude Code 2.1.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from narcisse.llm.provider import LLMError, Reply, Status, Task, validated

log = logging.getLogger(__name__)

DEFAULT_MODEL = "haiku"
# Aliases the CLI resolves to its latest model of each family.
MODELS = ("haiku", "sonnet", "opus")
TIMEOUT = 180.0
STATUS_TIMEOUT = 20.0
# No console window flashing up when Narcisse runs in the background (pythonw).
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Runs a command with this input and time limit: (exit code, stdout, stderr).
Runner = Callable[[list[str], bytes, float], Awaitable[tuple[int, bytes, bytes]]]


def find() -> str | None:
    """The `claude` command: on the PATH, or where its installer puts it (a process started
    before the install doesn't see the new PATH)."""
    found = shutil.which("claude")
    if found:
        return found
    home = Path.home() / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude")
    return str(home) if home.is_file() else None


async def run(args: list[str], stdin: bytes, limit: float) -> tuple[int, bytes, bytes]:
    def blocking() -> tuple[int, bytes, bytes]:
        with tempfile.TemporaryDirectory(prefix="narcisse-llm-") as empty:
            done = subprocess.run(
                args,
                input=stdin,
                capture_output=True,
                timeout=limit,
                cwd=empty,
                creationflags=NO_WINDOW,
                check=False,
            )
        return done.returncode, done.stdout, done.stderr

    try:
        return await asyncio.to_thread(blocking)
    except subprocess.TimeoutExpired as exc:
        raise LLMError("llm_timeout") from exc
    except OSError as exc:
        log.warning("could not run Claude Code: %s", exc)
        raise LLMError("llm_missing") from exc


def _failure(text: str, status: Any) -> LLMError:
    """The error behind a failed answer, from what the CLI says."""
    lowered = text.lower()
    signs = ("not logged in", "/login", "authentication", "oauth token", "invalid api key")
    if status in (401, 403) or any(w in lowered for w in signs):
        return LLMError("llm_not_logged_in")
    if status == 429 or any(w in lowered for w in ("usage limit", "rate limit", "limit reached")):
        return LLMError("llm_quota")
    return LLMError("llm_failed")


class ClaudeCode:
    name = "claude_code"
    remote = True

    def __init__(
        self, model: str | None = None, *, command: str | None = None, runner: Runner = run
    ) -> None:
        self.model: str | None = model or DEFAULT_MODEL
        self._command = command
        self._run = runner

    def _command_or_fail(self) -> str:
        command = self._command or find()
        if command is None:
            raise LLMError("llm_missing")
        return command

    async def status(self) -> Status:
        try:
            command = self._command_or_fail()
            code, out, _ = await self._run([command, "auth", "status"], b"", STATUS_TIMEOUT)
        except LLMError as exc:
            return Status(False, exc.code)
        try:
            logged_in = json.loads(out).get("loggedIn")
        except (ValueError, AttributeError):
            logged_in = None
        if logged_in is False or (code != 0 and logged_in is None):
            return Status(False, "llm_not_logged_in")
        return Status(True)

    async def ask(self, task: Task, prompt: str) -> Reply:
        command = self._command_or_fail()
        args = [
            command,
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(task.schema),
            "--system-prompt",
            task.instructions,
            "--model",
            self.model or DEFAULT_MODEL,
            "--tools",
            "",
            "--no-session-persistence",
            "--safe-mode",
            "--strict-mcp-config",
            "--disable-slash-commands",
        ]
        code, out, err = await self._run(args, prompt.encode("utf-8"), TIMEOUT)
        try:
            result: dict[str, Any] = json.loads(out)
        except ValueError:
            log.warning("Claude Code answered no JSON (exit %s): %s", code, err[:500])
            raise _failure(err.decode("utf-8", "replace"), None) from None
        if result.get("is_error") or result.get("subtype") != "success":
            log.warning("Claude Code failed: %s", str(result.get("result"))[:500])
            raise _failure(str(result.get("result") or ""), result.get("api_error_status"))
        data = result.get("structured_output")
        if data is None:
            try:
                data = json.loads(result.get("result") or "")
            except ValueError as exc:
                raise LLMError("llm_unreadable") from exc
        models = list(result.get("modelUsage") or {})
        return Reply(validated(task, data), models[0] if models else self.model)
