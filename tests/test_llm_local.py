"""Models on this machine or behind any OpenAI-compatible address: the provider, the machine's
resources and the model that suits them, the servers found, and downloading a model."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from narcisse.api import assistant as assistant_api
from narcisse.llm import machine
from narcisse.llm.local import Puller, probe
from narcisse.llm.machine import Gpu, Machine, recommend
from narcisse.llm.openai_compat import OpenAICompatible, is_loopback
from narcisse.llm.provider import LLMError
from narcisse.llm.tasks import TRIAGE
from narcisse.preferences import Preferences
from tests.conftest import ApiFactory

VERDICT = {"verdict": "me", "reason": "Le pseudo et la ville correspondent."}
Handler = Callable[[httpx.Request], httpx.Response]


def client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def completion(content: Any, model: str = "gemma3:4b") -> httpx.Response:
    text = content if isinstance(content, str) else json.dumps(content)
    return httpx.Response(
        200, json={"model": model, "choices": [{"message": {"role": "assistant", "content": text}}]}
    )


# The provider


async def test_a_question_asks_for_the_answers_shape() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return completion(VERDICT)

    provider = OpenAICompatible("local", client(handler), None, "gemma3:4b")
    reply = await provider.ask(TRIAGE, "La trace : compte « jeanne »")

    assert (reply.data, reply.model) == (VERDICT, "gemma3:4b")
    [request] = seen
    assert str(request.url) == "http://127.0.0.1:11434/v1/chat/completions"  # Ollama by default
    body = json.loads(request.content)
    assert body["response_format"]["json_schema"]["schema"] == TRIAGE.schema
    assert body["messages"][1]["content"] == "La trace : compte « jeanne »"
    assert "authorization" not in request.headers  # no key given, none sent
    assert request.headers["user-agent"].startswith("Narcisse/")


async def test_a_server_without_schemas_gets_the_shape_in_the_instructions() -> None:
    bodies: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return httpx.Response(400, json={"error": "response_format not supported"})
        return completion(f"```json\n{json.dumps(VERDICT)}\n```")

    provider = OpenAICompatible("openai", client(handler), "https://llm.example.org", "m", "k")
    reply = await provider.ask(TRIAGE, "…")

    assert reply.data == VERDICT
    assert bodies[1]["response_format"] == {"type": "json_object"}
    assert "verdict" in bodies[1]["messages"][0]["content"]


async def test_a_key_is_sent_to_the_service_only() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return completion(VERDICT)

    provider = OpenAICompatible("openai", client(handler), "https://llm.example.org/", "m", "k-1")
    await provider.ask(TRIAGE, "…")
    assert seen[0].url.host == "llm.example.org"
    assert seen[0].headers["authorization"] == "Bearer k-1"
    assert provider.remote is True


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (httpx.Response(401), "llm_key_rejected"),
        (httpx.Response(404), "llm_model_missing"),
        (httpx.Response(429), "llm_quota"),
        (httpx.Response(500, text="boom"), "llm_failed"),
        (completion("pas du JSON"), "llm_unreadable"),
        (completion({"verdict": "peut-être"}), "llm_unreadable"),
    ],
)
async def test_what_a_failed_answer_means(answer: httpx.Response, code: str) -> None:
    provider = OpenAICompatible("local", client(lambda _: answer), None, "m")
    with pytest.raises(LLMError) as raised:
        await provider.ask(TRIAGE, "…")
    assert raised.value.code == code


async def test_a_server_that_does_not_answer_says_so() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    provider = OpenAICompatible("local", client(handler), None, "m")
    with pytest.raises(LLMError) as raised:
        await provider.ask(TRIAGE, "…")
    assert raised.value.code == "llm_unreachable"
    assert (await provider.status()).reason == "llm_unreachable"


async def test_the_status_checks_the_model_is_there() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "gemma3:4b"}, {"id": "gemma3:1b"}]})

    ready = await OpenAICompatible("local", client(handler), None, "gemma3:4b").status()
    assert (ready.available, ready.models) == (True, ("gemma3:1b", "gemma3:4b"))
    missing = await OpenAICompatible("local", client(handler), None, "gemma3:12b").status()
    assert (missing.available, missing.reason) == (False, "llm_model_missing")
    unset = await OpenAICompatible("local", client(handler), None, None).status()
    assert unset.reason == "llm_model_unset"
    # A service may serve models it doesn't list.
    remote = OpenAICompatible("openai", client(handler), "https://llm.example.org", "other")
    assert (await remote.status()).available


@pytest.mark.parametrize(
    ("url", "local"),
    [
        ("http://127.0.0.1:11434", True),
        ("http://localhost:1234", True),
        ("http://[::1]:8080", True),
        ("http://192.168.1.20:11434", False),  # another machine at home: it leaves this one
        ("https://llm.example.org", False),
    ],
)
def test_only_a_loopback_address_is_local(url: str, local: bool) -> None:
    assert is_loopback(url) is local


# The machine


def commands(outputs: dict[str, str]) -> Callable[[list[str]], str | None]:
    return lambda args: outputs.get(args[0])


def test_a_linux_machine_with_an_nvidia_card(tmp_path: Path) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       32765432 kB\nMemFree: 1 kB\n")
    found = machine.detect(
        commands(
            {
                "lspci": "00:02.0 VGA compatible controller: Intel Corporation UHD Graphics\n"
                "01:00.0 VGA compatible controller: NVIDIA Corporation AD104",
                "nvidia-smi": "NVIDIA GeForce RTX 4070, 12282\n",
            }
        ),
        system="Linux",
        meminfo=meminfo,
    )
    assert found.memory_gb == 31.2
    assert [g.name for g in found.gpus] == [
        "NVIDIA GeForce RTX 4070",
        "Intel Corporation UHD Graphics",
    ]
    assert found.gpu_memory_gb == pytest.approx(12.0, abs=0.1)
    assert recommend(found).model == "gemma3:12b"


def test_an_apple_silicon_mac_uses_its_unified_memory() -> None:
    found = machine.detect(
        commands({"sysctl": str(16 * 2**30)}), system="Darwin", meminfo=Path("/nowhere")
    )
    # Both sysctl calls answer the same here: the brand string doesn't start with "Apple".
    assert (found.memory_gb, found.unified) == (16.0, False)
    apple = Machine("Darwin", 16.0, 8, (), unified=True)
    assert recommend(apple).model == "gemma3:4b"
    assert recommend(apple).speed == "fast"


def test_windows_cards_are_read_from_the_system() -> None:
    listed = json.dumps(
        [{"Name": "Intel(R) Iris(R) Xe Graphics"}, {"Name": "NVIDIA GeForce MX450"}]
    )
    found = machine.detect(commands({"powershell": listed}), system="Windows")
    assert [(g.name, g.dedicated) for g in found.gpus] == [
        ("Intel(R) Iris(R) Xe Graphics", False),
        ("NVIDIA GeForce MX450", True),
    ]


def test_what_cannot_be_read_is_unknown_not_an_error(tmp_path: Path) -> None:
    found = machine.detect(commands({}), system="Linux", meminfo=tmp_path / "missing")
    assert (found.memory_gb, found.gpus) == (None, ())
    assert recommend(found).model == "gemma3:1b"


@pytest.mark.parametrize(
    ("memory", "gpus", "model"),
    [
        (8.0, (), "gemma3:1b"),
        (16.0, (Gpu("Intel Iris Xe", None, False),), "gemma3:4b"),  # on the processor
        (16.0, (Gpu("RTX 3060", 12.0, True),), "gemma3:12b"),
        (64.0, (Gpu("RTX 4090", 24.0, True),), "gemma3:27b"),
    ],
)
def test_the_model_recommended_suits_the_machine(
    memory: float, gpus: tuple[Gpu, ...], model: str
) -> None:
    recommended = recommend(Machine("Linux", memory, 8, gpus))
    assert recommended.model == model
    assert recommended.size_gb > 0


# Local servers and downloads


async def test_the_servers_that_answer_are_listed_with_their_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.port == 11434:
            return httpx.Response(200, json={"data": [{"id": "gemma3:4b"}]})
        raise httpx.ConnectError("refused", request=request)

    [server] = await probe(client(handler))
    assert (server.name, server.url, server.models) == (
        "Ollama",
        "http://127.0.0.1:11434",
        ("gemma3:4b",),
    )


def pull_lines(*lines: dict[str, Any]) -> bytes:
    return b"".join(json.dumps(line).encode() + b"\n" for line in lines)


async def test_a_download_follows_its_progress_and_chooses_the_model(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    Preferences(llm_provider="local").save(path)

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://127.0.0.1:11434/api/pull"
        assert json.loads(request.content) == {"model": "gemma3:4b", "stream": True}
        return httpx.Response(
            200,
            content=pull_lines(
                {"status": "pulling manifest"},
                {"status": "pulling a", "digest": "a", "total": 300, "completed": 100},
                {"status": "pulling b", "digest": "b", "total": 100, "completed": 100},
                {"status": "pulling a", "digest": "a", "total": 300, "completed": 300},
                {"status": "success"},
            ),
        )

    puller = Puller(client(handler), path)
    puller.start("gemma3:4b")
    assert puller.state.status == "pulling"
    assert puller._task is not None
    await puller._task

    assert (puller.state.status, puller.state.completed, puller.state.total) == ("done", 400, 400)
    assert Preferences.load(path).llm_model == "gemma3:4b"


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (
            httpx.Response(
                200, content=pull_lines({"error": "pull model manifest: file does not exist"})
            ),
            "pull_failed",
        ),
        (httpx.Response(404), "llm_model_missing"),
        (httpx.Response(200, content=pull_lines({"status": "pulling manifest"})), "pull_failed"),
    ],
)
async def test_a_failed_download_says_why(
    tmp_path: Path, answer: httpx.Response, code: str
) -> None:
    puller = Puller(client(lambda _: answer), tmp_path / "preferences.json")
    puller.start("gemma3:4b")
    assert puller._task is not None
    await puller._task
    assert (puller.state.status, puller.state.error_code) == ("failed", code)


async def test_without_ollama_the_download_says_so(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    puller = Puller(client(handler), tmp_path / "preferences.json")
    puller.start("gemma3:4b")
    assert puller._task is not None
    await puller._task
    assert puller.state.error_code == "ollama_missing"


async def test_the_api_reads_the_machine_and_refuses_downloads_in_demo(
    make_api: ApiFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        assistant_api, "_machine", lambda: Machine("Linux", 16.0, 8, (Gpu("Iris Xe", None, False),))
    )

    def ollama(request: httpx.Request) -> httpx.Response:
        if request.url.port == 11434 and request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "gemma3:1b"}]})
        raise httpx.ConnectError("refused", request=request)

    demo = await make_api(http_transport=httpx.MockTransport(ollama))
    found = await demo.json("GET", "/assistant/machine")
    assert (found["memory_gb"], found["recommended"]["model"]) == (16.0, "gemma3:4b")
    assert found["servers"] == [
        {"name": "Ollama", "url": "http://127.0.0.1:11434", "models": ["gemma3:1b"]}
    ]
    error = await demo.json("POST", "/assistant/pull", {"model": "gemma3:4b"}, status=409)
    assert error["code"] == "llm_provider_unavailable"
    assert (await demo.json("GET", "/assistant/pull"))["status"] == "idle"
    await demo.json("POST", "/assistant/pull", {"model": "x; rm -rf"}, status=422)


async def test_a_local_assistant_answers_through_the_api(make_api: ApiFactory) -> None:
    def ollama(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "gemma3:4b"}]})
        return completion(VERDICT)

    api = await make_api(None, demo=False, http_transport=httpx.MockTransport(ollama))
    await api.json("PATCH", "/preferences", {"llm_provider": "local", "llm_model": "gemma3:4b"})
    status = await api.json("GET", "/assistant")
    assert (status["provider"], status["remote"], status["available"]) == ("local", False, True)
    assert status["models"] == ["gemma3:4b"]
    assert (await api.json("POST", "/assistant/try", status=502))["code"] == "llm_unreadable"

    await api.json(
        "PATCH", "/preferences", {"llm_provider": "openai", "llm_url": "pas une url"}, 422
    )
    await api.json(
        "PATCH", "/preferences", {"llm_provider": "openai", "llm_url": "https://llm.example.org/"}
    )
    shown = await api.json("GET", "/preferences")
    assert shown["llm_url"] == "https://llm.example.org"
    remote = await api.json("GET", "/assistant")
    assert remote["remote"] is True
    assert (await api.json("POST", "/assistant/try", status=409))["code"] == "llm_remote_consent"
