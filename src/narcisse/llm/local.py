"""Model servers on this machine: which ones answer, what models they have, and downloading the
recommended model into Ollama when the user asks.

Only loopback addresses are contacted here. Narcisse installs no server: it finds the ones the
user installed, and asks Ollama (its own API) to download a model after the user confirmed.
"""

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, replace
from pathlib import Path

import httpx

from narcisse.errors import AppError
from narcisse.llm.openai_compat import OLLAMA, OpenAICompatible, is_loopback
from narcisse.llm.provider import LLMError
from narcisse.preferences import Preferences

log = logging.getLogger(__name__)

# Where each server listens out of the box.
SERVERS = (
    ("Ollama", OLLAMA),
    ("LM Studio", "http://127.0.0.1:1234"),
    ("llama.cpp", "http://127.0.0.1:8080"),
)
# A download is slow, but a server that stops talking for that long has stopped.
PULL_TIMEOUT = httpx.Timeout(30.0, read=600.0)


@dataclass(frozen=True)
class LocalServer:
    name: str
    url: str
    models: tuple[str, ...]


async def probe(client: httpx.AsyncClient) -> list[LocalServer]:
    """The servers that answer, with their models."""

    async def one(name: str, url: str) -> LocalServer | None:
        try:
            models = await OpenAICompatible("local", client, url, None).models()
        except LLMError:
            return None
        return LocalServer(name, url, models)

    found = await asyncio.gather(*(one(name, url) for name, url in SERVERS))
    return [server for server in found if server is not None]


@dataclass(frozen=True)
class PullState:
    model: str | None = None
    status: str = "idle"  # idle, pulling, done, failed, cancelled
    completed: int = 0  # bytes
    total: int = 0  # bytes (0 until Ollama says)
    error_code: str | None = None


class Puller:
    """One download at a time, followed by the activity centre (it polls `state`)."""

    def __init__(self, client: httpx.AsyncClient, preferences_path: Path) -> None:
        self._client = client
        self._preferences_path = preferences_path
        self.state = PullState()
        self._task: asyncio.Task[None] | None = None

    def start(self, model: str) -> PullState:
        if self.state.status == "pulling":
            raise AppError("pull_running", status=409)
        preferences = Preferences.load(self._preferences_path)
        url = preferences.llm_url if preferences.llm_url else OLLAMA
        if preferences.llm_provider != "local" or not is_loopback(url):
            url = OLLAMA
        self.state = PullState(model=model, status="pulling")
        self._task = asyncio.create_task(self._pull(url, model), name="model-pull")
        return self.state

    async def cancel(self) -> PullState:
        if self._task is not None and self.state.status == "pulling":
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self.state = replace(self.state, status="cancelled")
        return self.state

    async def stop(self) -> None:
        await self.cancel()

    def _failed(self, code: str) -> None:
        self.state = replace(self.state, status="failed", error_code=code)

    async def _pull(self, url: str, model: str) -> None:
        totals: dict[str, int] = {}
        done: dict[str, int] = {}
        try:
            async with self._client.stream(
                "POST",
                f"{url}/api/pull",
                json={"model": model, "stream": True},
                timeout=PULL_TIMEOUT,
            ) as response:
                if response.status_code != 200:
                    await response.aread()
                    log.warning("Ollama refused to pull %s: %s", model, response.text[:300])
                    self._failed(
                        "llm_model_missing" if response.status_code == 404 else "pull_failed"
                    )
                    return
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except ValueError:
                        continue
                    if data.get("error"):
                        log.warning("Ollama could not pull %s: %s", model, data["error"])
                        self._failed("pull_failed")
                        return
                    digest = data.get("digest")
                    if digest and data.get("total"):
                        totals[digest] = int(data["total"])
                        done[digest] = int(data.get("completed") or 0)
                        self.state = replace(
                            self.state, completed=sum(done.values()), total=sum(totals.values())
                        )
                    if data.get("status") == "success":
                        self.state = replace(self.state, status="done", completed=self.state.total)
                        self._choose(model)
                        return
            self._failed("pull_failed")  # the stream ended without saying it succeeded
        except httpx.HTTPError:
            self._failed("ollama_missing")

    def _choose(self, model: str) -> None:
        """A model downloaded for the local assistant becomes its model."""
        preferences = Preferences.load(self._preferences_path)
        if preferences.llm_provider == "local":
            replace(preferences, llm_model=model).save(self._preferences_path)
