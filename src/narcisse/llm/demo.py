"""Demo mode's assistant: fixed answers after a short wait, so the UI can be shown and tested
without any model. It answers the same way for the same text."""

import hashlib
import re
from typing import Any

from narcisse.clock import Clock
from narcisse.llm.provider import LLMError, Reply, Status, Task, validated

THINKING = 2.0  # seconds, on the demo clock
VERDICTS = ("me", "not_me", "unsure")
REASONS = {
    "me": "Les preuves reprennent ton nom et un pseudo que tu as déclaré.",
    "not_me": "Le nom correspond, mais la ville et le métier décrits ne sont pas les tiens.",
    "unsure": "Le pseudo est identique, mais rien d’autre ne relie ce compte à toi.",
}
ADDED = "Je précise que ce compte n’est plus utilisé depuis plusieurs années."
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SITE = re.compile(r"https?://([\w-]+(?:\.[\w-]+)+)")


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
        data: dict[str, Any]
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
        elif task.name == "letter":
            subject = prompt.split("<objet>", 1)[-1].split("</objet>", 1)[0]
            body = prompt.split("<texte>", 1)[-1].split("</texte>", 1)[0]
            data = {"subject": subject, "body": f"{ADDED}\n\n{body}"}
        elif task.name == "leads":
            proofs = prompt.split("Ses preuves :", 1)[-1]
            found = [("email", e) for e in EMAIL.findall(proofs)]
            found += [("domain", d) for d in SITE.findall(proofs)]
            data = {
                "leads": [
                    {"kind": kind, "value": value, "reason": "Cité dans une des preuves."}
                    for kind, value in dict.fromkeys(found)
                ][:3]
            }
        elif task.name == "try":
            data = {"answer": "ok"}
        else:
            raise LLMError("llm_failed")
        return Reply(validated(task, data), self.model)
