"""The Claude Code provider, with the CLI faked: what it is run with, and what its answers mean."""

import json
import sys
from typing import Any

import pytest

from narcisse.llm import claude_code
from narcisse.llm.claude_code import ClaudeCode
from narcisse.llm.provider import LLMError
from narcisse.llm.tasks import TRIAGE


class FakeCli:
    """Answers as `claude` would, and remembers how it was run."""

    def __init__(self, stdout: Any = None, *, code: int = 0, stderr: bytes = b"") -> None:
        self.stdout = stdout
        self.code = code
        self.stderr = stderr
        self.calls: list[tuple[list[str], bytes, float]] = []

    async def __call__(
        self, args: list[str], stdin: bytes, limit: float
    ) -> tuple[int, bytes, bytes]:
        self.calls.append((args, stdin, limit))
        out = self.stdout if isinstance(self.stdout, bytes) else json.dumps(self.stdout).encode()
        return self.code, out, self.stderr


def success(**fields: Any) -> dict[str, Any]:
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "",
        "modelUsage": {"claude-haiku-5-5": {}},
        **fields,
    }


VERDICT = {"verdict": "not_me", "reason": "Une autre ville."}


async def test_a_question_runs_claude_without_tools_settings_or_session() -> None:
    cli = FakeCli(success(structured_output=VERDICT))
    provider = ClaudeCode(command="claude", runner=cli)

    reply = await provider.ask(TRIAGE, "La trace : compte « jeanne »")

    assert reply.data == VERDICT
    assert reply.model == "claude-haiku-5-5"
    [(args, stdin, _)] = cli.calls
    assert args[:2] == ["claude", "-p"]
    assert stdin.decode() == "La trace : compte « jeanne »"  # the data goes on stdin, not argv
    tools = args.index("--tools")
    assert args[tools + 1] == ""  # no tool at all
    for flag in ("--no-session-persistence", "--safe-mode", "--strict-mcp-config"):
        assert flag in args
    assert args[args.index("--model") + 1] == "haiku"
    assert json.loads(args[args.index("--json-schema") + 1]) == TRIAGE.schema
    assert args[args.index("--system-prompt") + 1] == TRIAGE.system


async def test_the_model_chosen_is_passed_on() -> None:
    cli = FakeCli(success(structured_output=VERDICT))
    await ClaudeCode("sonnet", command="claude", runner=cli).ask(TRIAGE, "…")
    args = cli.calls[0][0]
    assert args[args.index("--model") + 1] == "sonnet"


async def test_an_answer_given_as_text_is_read_too() -> None:
    cli = FakeCli(success(result=json.dumps(VERDICT)))
    reply = await ClaudeCode(command="claude", runner=cli).ask(TRIAGE, "…")
    assert reply.data == VERDICT


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (success(structured_output={"verdict": "maybe", "reason": "?"}), "llm_unreadable"),
        (success(result="Je pense que oui."), "llm_unreadable"),
        ({"subtype": "error", "is_error": True, "api_error_status": 429}, "llm_quota"),
        (
            {"subtype": "success", "is_error": True, "result": "Not logged in · Please run /login"},
            "llm_not_logged_in",
        ),
        ({"subtype": "error_max_turns", "is_error": False, "result": ""}, "llm_failed"),
        (b"Error: something broke", "llm_failed"),
    ],
)
async def test_what_a_failed_answer_means(answer: Any, code: str) -> None:
    cli = FakeCli(answer, code=1 if isinstance(answer, bytes) else 0)
    with pytest.raises(LLMError) as raised:
        await ClaudeCode(command="claude", runner=cli).ask(TRIAGE, "…")
    assert raised.value.code == code


async def test_a_missing_cli_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(claude_code, "find", lambda: None)
    provider = ClaudeCode(runner=FakeCli(success()))
    assert (await provider.status()).reason == "llm_missing"
    with pytest.raises(LLMError) as raised:
        await provider.ask(TRIAGE, "…")
    assert raised.value.code == "llm_missing"


async def test_the_status_reads_whether_the_user_is_logged_in() -> None:
    logged_in = FakeCli({"loggedIn": True, "authMethod": "claude.ai"})
    assert (await ClaudeCode(command="claude", runner=logged_in).status()).available
    assert logged_in.calls[0][0] == ["claude", "auth", "status"]

    logged_out = FakeCli({"loggedIn": False}, code=1)
    status = await ClaudeCode(command="claude", runner=logged_out).status()
    assert (status.available, status.reason) == (False, "llm_not_logged_in")


async def test_a_command_that_takes_too_long_is_stopped() -> None:
    with pytest.raises(LLMError) as raised:
        await claude_code.run([sys.executable, "-c", "import time; time.sleep(5)"], b"", 0.2)
    assert raised.value.code == "llm_timeout"


async def test_a_command_that_does_not_exist_counts_as_missing(tmp_path: Any) -> None:
    with pytest.raises(LLMError) as raised:
        await claude_code.run([str(tmp_path / "no-claude-here")], b"", 5)
    assert raised.value.code == "llm_missing"
