"""What every provider offers, and the errors the UI can explain."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel

from narcisse.i18n import Lang, Text, pick


class LLMError(Exception):
    """Why a provider couldn't answer: a code the UI translates (`llm_missing`, `llm_quota`…)."""

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


@dataclass(frozen=True)
class Task:
    """One thing the assistant is asked: its instructions and the shape of its answer."""

    name: str
    system: Text  # the instructions, in both languages
    output: type[BaseModel]

    @property
    def schema(self) -> dict[str, Any]:
        return self.output.model_json_schema()

    @property
    def instructions(self) -> str:
        """The instructions as sent (French, unless the task was localized)."""
        return pick(self.system, "fr")

    def localized(self, lang: Lang) -> "Task":
        """The same task, with its instructions in this language."""
        return Task(self.name, pick(self.system, lang), self.output)


@dataclass(frozen=True)
class Reply:
    data: dict[str, Any]  # validated against the task's output
    model: str | None  # the model that answered, when the provider says


@dataclass(frozen=True)
class Status:
    available: bool
    reason: str | None = None  # an error code, when not available
    params: dict[str, Any] = field(default_factory=dict)
    models: tuple[str, ...] = ()  # the models the provider can be asked to use


class Provider(Protocol):
    name: str
    # Whether what is sent leaves the machine (the user must agree first).
    remote: bool
    model: str | None

    async def status(self) -> Status: ...

    async def ask(self, task: Task, prompt: str) -> Reply: ...


def validated(task: Task, data: Any) -> dict[str, Any]:
    """The answer in the task's shape, or `llm_unreadable`."""
    try:
        return task.output.model_validate(data).model_dump(mode="json")
    except ValueError as exc:
        raise LLMError("llm_unreadable") from exc
