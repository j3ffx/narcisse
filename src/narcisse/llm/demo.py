"""Demo mode's assistant: fixed answers after a short wait, so the UI can be shown and tested
without any model. It answers the same way for the same text."""

import hashlib

from narcisse.clock import Clock
from narcisse.llm.provider import LLMError, Reply, Status, Task, validated

THINKING = 2.0  # seconds, on the demo clock
VERDICTS = ("me", "not_me", "unsure")
REASONS = {
    "me": "Les preuves reprennent ton nom et un pseudo que tu as déclaré.",
    "not_me": "Le nom correspond, mais la ville et le métier décrits ne sont pas les tiens.",
    "unsure": "Le pseudo est identique, mais rien d’autre ne relie ce compte à toi.",
}


class Demo:
    name = "demo"
    remote = False
    model: str | None = "démo"

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    async def status(self) -> Status:
        return Status(True)

    async def ask(self, task: Task, prompt: str) -> Reply:
        await self._clock.sleep(THINKING)
        pick = hashlib.sha256(prompt.encode("utf-8")).digest()[0]
        if task.name == "triage":
            verdict = VERDICTS[pick % len(VERDICTS)]
            data = {"verdict": verdict, "reason": REASONS[verdict]}
        elif task.name == "explain":
            data = {
                "summary": "Un compte public à ton nom, ouvert sur un site fictif de "
                "démonstration.",
                "risk": "Il relie ton pseudo à ton nom : quelqu’un qui connaît l’un retrouve "
                "l’autre. Rien de sensible n’y est affiché.",
            }
        elif task.name == "try":
            data = {"answer": "ok"}
        else:
            raise LLMError("llm_failed")
        return Reply(validated(task, data), self.model)
