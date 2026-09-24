"""Tests for the recording LLM wrapper."""

import pytest

from pythia.recording import NullRecorder, RecordingLLMClient, infer_provider, parse_model_spec
from tests.conftest import FakeLLMClient


class FakeRecorder:
    def __init__(self, model_map=None):
        self.calls = []
        self.model_map = model_map or {}

    def record_llm_call(self, **kw):
        self.calls.append(kw)

    def model_for(self, requested_model):
        return self.model_map.get(requested_model)


def _inner(response, model="inner-model"):
    c = FakeLLMClient(responses=[response])
    c.model = model
    c.provider_name = "fake"
    return c


async def test_delegates_and_records():
    inner = _inner({"ok": 1})
    rec = FakeRecorder()
    client = RecordingLLMClient(inner, role="tick", recorder=rec)
    out = await client.generate("hello", system="sys")
    assert out == {"ok": 1}
    assert len(rec.calls) == 1
    call = rec.calls[0]
    assert call["role"] == "tick"
    assert call["requested_model"] == "inner-model"
    assert call["model"] == "inner-model"
    assert call["provider"] == "fake"
    assert call["prompt"] == "hello" and call["system"] == "sys"
    assert call["response"] == {"ok": 1}
    assert call["latency_ms"] >= 0
    assert call["started_at"] <= call["ended_at"]


async def test_model_map_routes_only_matching_model():
    tick_inner = _inner({"from": "inner"}, model="llama-3.1-8b-instant")
    main_inner = _inner({"from": "main"}, model="llama-3.3-70b-versatile")
    alt = _inner({"from": "alt"}, model="gpt-4o-mini")
    built = []

    def factory(model):
        built.append(model)
        return alt

    rec = FakeRecorder(model_map={"llama-3.1-8b-instant": "gpt-4o-mini"})
    tick = RecordingLLMClient(tick_inner, role="tick", recorder=rec, factory=factory)
    main = RecordingLLMClient(main_inner, role="main", recorder=rec, factory=factory)

    assert await tick.generate("p") == {"from": "alt"}
    assert await main.generate("p") == {"from": "main"}
    assert built == ["gpt-4o-mini"]
    assert rec.calls[0]["requested_model"] == "llama-3.1-8b-instant"
    assert rec.calls[0]["model"] == "gpt-4o-mini"


async def test_override_client_is_built_once():
    alt = FakeLLMClient(responses=[{"a": 1}, {"a": 2}])
    alt.model = "gpt-4o-mini"
    count = []

    def factory(model):
        count.append(model)
        return alt

    rec = FakeRecorder(model_map={"inner-model": "gpt-4o-mini"})
    client = RecordingLLMClient(_inner({}), role="tick", recorder=rec, factory=factory)
    await client.generate("1")
    await client.generate("2")
    assert len(count) == 1


async def test_null_recorder_is_transparent():
    client = RecordingLLMClient(_inner({"x": 1}), role="main", recorder=NullRecorder())
    assert await client.generate("p") == {"x": 1}


def test_parse_model_spec():
    assert parse_model_spec("openai:gpt-4o-mini") == ("openai", "gpt-4o-mini")
    with pytest.raises(ValueError):
        parse_model_spec("gpt-4o-mini")


def test_infer_provider():
    assert infer_provider("gpt-4o-mini") == ("openai", "gpt-4o-mini")
    assert infer_provider("llama-3.1-8b-instant") == ("groq", "llama-3.1-8b-instant")
    assert infer_provider("claude-haiku-4-5") == ("anthropic", "claude-haiku-4-5")
    assert infer_provider("openai:gpt-4o") == ("openai", "gpt-4o")
    assert infer_provider("openai/gpt-oss-20b") == ("groq", "openai/gpt-oss-20b")
    with pytest.raises(ValueError):
        infer_provider("mystery")
