"""Tests for OpenAICompatClient retry behaviour."""

import httpx
import pytest

from pythia.openai_compat_client import OpenAICompatClient

OK = {"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


def _client(statuses: list[int], seen: list | None = None) -> OpenAICompatClient:
    queue = list(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        status = queue.pop(0) if queue else 200
        return httpx.Response(status, json=OK if status == 200 else {"error": {"message": "x"}})

    return OpenAICompatClient(api_key="k", model="gpt-4o-mini", base_url="https://api.test/v1/chat/completions",
                              http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_):
        return None
    monkeypatch.setattr("pythia.openai_compat_client.asyncio.sleep", instant)


@pytest.mark.parametrize("status", [500, 502, 503, 504])
async def test_transient_server_errors_are_retried(status):
    seen = []
    assert await _client([status, status], seen).generate("p") == {"ok": True}
    assert len(seen) == 3


async def test_client_errors_are_not_retried():
    seen = []
    with pytest.raises(httpx.HTTPStatusError):
        await _client([400], seen).generate("p")
    assert len(seen) == 1


async def test_timeouts_are_retried():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json=OK)

    client = OpenAICompatClient(api_key="k", model="gpt-4o-mini", base_url="https://api.test/v1/chat/completions",
                                http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await client.generate("p") == {"ok": True}
    assert len(calls) == 2
