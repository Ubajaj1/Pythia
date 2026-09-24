"""Tests for LLM client abstraction and Ollama client."""

import json
import pytest
import httpx
from pythia.llm import LLMClient, OllamaClient


class TestLLMClientProtocol:
    """Verify the FakeLLMClient satisfies the protocol."""

    @pytest.fixture
    def fake_client(self):
        from tests.conftest import FakeLLMClient
        return FakeLLMClient(responses=[{"result": "hello"}])

    async def test_fake_client_returns_canned_response(self, fake_client):
        result = await fake_client.generate("test prompt")
        assert result == {"result": "hello"}

    async def test_fake_client_records_calls(self, fake_client):
        await fake_client.generate("test prompt", system="sys")
        assert len(fake_client.calls) == 1
        assert fake_client.calls[0]["prompt"] == "test prompt"
        assert fake_client.calls[0]["system"] == "sys"

    async def test_fake_client_pops_responses_in_order(self, fake_client):
        fake_client.responses = [{"a": 1}, {"b": 2}]
        r1 = await fake_client.generate("p1")
        r2 = await fake_client.generate("p2")
        assert r1 == {"a": 1}
        assert r2 == {"b": 2}


class TestOllamaClient:
    """Test OllamaClient with mocked HTTP transport."""

    def _make_transport(self, response_body: dict) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"response": json.dumps(response_body)},
            )
        return httpx.MockTransport(handler)

    async def test_generate_parses_json_response(self):
        transport = self._make_transport({"stance": 0.5})
        client = OllamaClient(
            base_url="http://fake:11434",
            model="test-model",
            http_client=httpx.AsyncClient(transport=transport),
        )
        result = await client.generate("What is your stance?")
        assert result == {"stance": 0.5}

    async def test_generate_sends_correct_payload(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"response": '{"ok": true}'})

        transport = httpx.MockTransport(handler)
        client = OllamaClient(
            base_url="http://fake:11434",
            model="test-model",
            http_client=httpx.AsyncClient(transport=transport),
        )
        await client.generate("my prompt", system="my system")
        assert captured["body"]["model"] == "test-model"
        assert captured["body"]["prompt"] == "my prompt"
        assert captured["body"]["system"] == "my system"
        assert captured["body"]["format"] == "json"
        assert captured["body"]["stream"] is False

    async def test_generate_retries_on_malformed_json(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json={"response": "not valid json {{"})
            return httpx.Response(200, json={"response": '{"recovered": true}'})

        transport = httpx.MockTransport(handler)
        client = OllamaClient(
            base_url="http://fake:11434",
            model="test-model",
            http_client=httpx.AsyncClient(transport=transport),
        )
        result = await client.generate("prompt")
        assert result == {"recovered": True}
        assert call_count == 2

    async def test_connection_error_gives_clear_message(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(handler)
        client = OllamaClient(
            base_url="http://fake:11434",
            model="test-model",
            http_client=httpx.AsyncClient(transport=transport),
        )
        with pytest.raises(ConnectionError, match="Cannot connect to Ollama"):
            await client.generate("prompt")

    async def test_http_error_gives_clear_message(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "model not found"})

        transport = httpx.MockTransport(handler)
        client = OllamaClient(
            base_url="http://fake:11434",
            model="nonexistent-model",
            http_client=httpx.AsyncClient(transport=transport),
        )
        with pytest.raises(RuntimeError, match="Ollama returned HTTP 404"):
            await client.generate("prompt")


from pythia import llm as llm_mod


def test_parse_model_spec():
    assert llm_mod.parse_model_spec("anthropic:claude-haiku-4-5") == ("anthropic", "claude-haiku-4-5")
    with pytest.raises(ValueError):
        llm_mod.parse_model_spec("claude-haiku-4-5")


def test_role_env_specs_win(monkeypatch):
    built = []
    monkeypatch.setattr(llm_mod, "build_llm_client", lambda provider=None, ollama_url=None, model=None: built.append((provider, model)) or (provider, model))
    monkeypatch.setenv("PYTHIA_MAIN_MODEL", "openai:gpt-4o-mini")
    monkeypatch.setenv("PYTHIA_TICK_MODEL", "groq:openai/gpt-oss-20b")
    main, tick = llm_mod.build_role_clients()
    assert main == ("openai", "gpt-4o-mini")
    assert tick == ("groq", "openai/gpt-oss-20b")


def test_anthropic_default_gets_haiku_tick(monkeypatch):
    monkeypatch.delenv("PYTHIA_MAIN_MODEL", raising=False)
    monkeypatch.delenv("PYTHIA_TICK_MODEL", raising=False)
    monkeypatch.setattr("pythia.config.ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(llm_mod, "build_llm_client", lambda provider=None, ollama_url=None, model=None: (provider, model))
    main, tick = llm_mod.build_role_clients()
    assert main == (None, None)
    assert tick == ("anthropic", "claude-haiku-4-5")


def test_explicit_model_disables_tick_split(monkeypatch):
    monkeypatch.delenv("PYTHIA_TICK_MODEL", raising=False)
    monkeypatch.delenv("PYTHIA_MAIN_MODEL", raising=False)
    monkeypatch.setattr(llm_mod, "build_llm_client", lambda provider=None, ollama_url=None, model=None: (provider, model))
    main, tick = llm_mod.build_role_clients(model="gpt-4o")
    assert tick is None


def test_groq_defaults_are_current_models(monkeypatch):
    # Groq retired the Llama 3.x models in 2026; the defaults must not point at them.
    import importlib
    from pythia import config
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("GROQ_FAST_MODEL", raising=False)
    fresh = importlib.reload(config)
    try:
        assert (fresh.GROQ_MODEL, fresh.GROQ_FAST_MODEL) == ("openai/gpt-oss-120b", "openai/gpt-oss-20b")
        assert fresh.GROQ_MODEL in llm_mod._GROQ_RPM_BY_MODEL
        assert fresh.GROQ_FAST_MODEL in llm_mod._GROQ_RPM_BY_MODEL
    finally:
        monkeypatch.undo()
        importlib.reload(config)
