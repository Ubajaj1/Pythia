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
