"""Any server that speaks OpenAI's chat completions API: a model on this machine (Ollama, LM
Studio, llama.cpp server) or a service elsewhere, at the address the user gave.

Only that address is ever contacted. It counts as local when it is a loopback address; anything
else, the home network included, leaves the machine and needs the user's agreement. The answer's
shape is asked for with `response_format` (a JSON schema); a server that refuses it is asked again
with the shape in the instructions, and the answer is checked the same way.
"""

import ipaddress
import json
import logging
from typing import Any
from urllib.parse import urlsplit

import httpx

from narcisse.engine.http import USER_AGENT
from narcisse.llm.provider import LLMError, Reply, Status, Task, validated

log = logging.getLogger(__name__)

# Ollama's address, where a local server is looked for first.
OLLAMA = "http://127.0.0.1:11434"
# A small model on a processor takes its time; a service elsewhere shouldn't.
LOCAL_TIMEOUT = 300.0
REMOTE_TIMEOUT = 120.0
STATUS_TIMEOUT = 5.0


def is_loopback(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _unfenced(content: str) -> str:
    """JSON some models wrap in a Markdown code block anyway."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    return text


def _error(response: httpx.Response) -> LLMError:
    status = response.status_code
    if status in (401, 403):
        return LLMError("llm_key_rejected")
    if status == 404:
        return LLMError("llm_model_missing")
    if status == 429:
        return LLMError("llm_quota")
    log.warning("the assistant's server answered %s: %s", status, response.text[:500])
    return LLMError("llm_failed", status=status)


class OpenAICompatible:
    def __init__(
        self,
        name: str,
        client: httpx.AsyncClient,
        url: str | None,
        model: str | None,
        key: str | None = None,
    ) -> None:
        self.name = name
        self.model: str | None = model
        self._client = client
        self._url = (url or (OLLAMA if name == "local" else "")).rstrip("/")
        self._key = key
        self.remote = not is_loopback(self._url) if self._url else name != "local"

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": USER_AGENT}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        return headers

    async def _request(
        self, method: str, path: str, limit: float, body: Any = None
    ) -> httpx.Response:
        if not self._url:
            raise LLMError("llm_url_missing")
        try:
            return await self._client.request(
                method,
                f"{self._url}{path}",
                json=body,
                headers=self._headers(),
                timeout=limit,
                follow_redirects=False,
            )
        except httpx.TimeoutException as exc:
            raise LLMError("llm_timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMError("llm_unreachable", address=self._url) from exc

    async def models(self) -> tuple[str, ...]:
        response = await self._request("GET", "/v1/models", STATUS_TIMEOUT)
        if response.status_code != 200:
            raise _error(response)
        try:
            data = response.json().get("data", [])
            return tuple(sorted(str(m["id"]) for m in data if isinstance(m, dict) and "id" in m))
        except (ValueError, AttributeError, KeyError):
            return ()

    async def status(self) -> Status:
        try:
            models = await self.models()
        except LLMError as exc:
            return Status(False, exc.code, exc.params)
        if not self.model:
            return Status(False, "llm_model_unset", models=models)
        # A service may serve models it doesn't list; a local server lists what it has.
        if not self.remote and models and self.model not in models:
            return Status(False, "llm_model_missing", {"model": self.model}, models)
        return Status(True, models=models)

    async def ask(self, task: Task, prompt: str) -> Reply:
        if not self.model:
            raise LLMError("llm_model_unset")
        timeout = REMOTE_TIMEOUT if self.remote else LOCAL_TIMEOUT
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": task.instructions},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": task.name, "schema": task.schema},
            },
        }
        response = await self._request("POST", "/v1/chat/completions", timeout, body)
        if response.status_code == 400:
            # A server that doesn't take a schema: the shape goes in the instructions instead.
            shape = json.dumps(task.schema, ensure_ascii=False)
            body["messages"][0]["content"] = f"{task.instructions}\n\nJSON schema: {shape}"
            body["response_format"] = {"type": "json_object"}
            response = await self._request("POST", "/v1/chat/completions", timeout, body)
        if response.status_code != 200:
            raise _error(response)
        try:
            answer = response.json()
            content = answer["choices"][0]["message"]["content"]
            data = json.loads(_unfenced(content))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("llm_unreadable") from exc
        return Reply(validated(task, data), answer.get("model") or self.model)
