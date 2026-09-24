"""Tests for KitaruRecorder using a fake async SDK."""

from datetime import datetime, timezone

import pytest

from pythia.kitaru_recorder import KitaruRecorder

T = datetime(2026, 9, 23, tzinfo=timezone.utc)


class FakeSDK:
    def __init__(self, model_map=None):
        self.started, self.nodes, self.finished, self.evals = [], [], [], []
        self.model_map = model_map or {}

    async def start_session(self, agent, inputs, name, metadata):
        self.started.append((agent, inputs, name, metadata))
        return "sess-1"

    async def ingest_llm_nodes(self, session_id, nodes):
        self.nodes.append((session_id, list(nodes)))

    async def finish_session(self, session_id, outputs, error):
        self.finished.append((session_id, outputs, error))

    async def read_model_map(self):
        return dict(self.model_map)

    async def write_evaluations(self, session_id, values):
        self.evals.append((session_id, dict(values)))


def _call(rec, role="tick"):
    rec.record_llm_call(role=role, requested_model="m", model="m", provider="groq", system="s",
                        prompt="p", response={"a": 1}, latency_ms=5, started_at=T, ended_at=T)


async def test_buffers_nodes_and_flushes_on_finish():
    sdk = FakeSDK()
    rec = KitaruRecorder(sdk=sdk)
    sid = await rec.start({"prompt": "q"}, name="q", metadata={"arm": "recorded"})
    _call(rec)
    _call(rec, role="main")
    assert sdk.nodes == []
    await rec.finish({"final": 0.3})
    assert sid == "sess-1"
    assert sdk.started == [("pythia-simulation", {"prompt": "q"}, "q", {"arm": "recorded"})]
    session_id, nodes = sdk.nodes[0]
    assert session_id == "sess-1" and len(nodes) == 2
    assert nodes[0]["external_id"] == "llm-0000" and nodes[0]["role"] == "tick"
    assert nodes[1]["role"] == "main"
    assert sdk.finished == [("sess-1", {"final": 0.3}, None)]


async def test_model_map_loaded_from_replay_unless_given():
    rec = KitaruRecorder(sdk=FakeSDK(model_map={"llama-3.1-8b-instant": "gpt-4o-mini"}))
    await rec.start({}, name="n", metadata={})
    assert rec.model_for("llama-3.1-8b-instant") == "gpt-4o-mini"
    assert rec.model_for("llama-3.3-70b-versatile") is None

    explicit = KitaruRecorder(sdk=FakeSDK(model_map={"x": "y"}), model_map={"a": "b"})
    await explicit.start({}, name="n", metadata={})
    assert explicit.model_for("a") == "b" and explicit.model_for("x") is None


async def test_failure_is_recorded():
    sdk = FakeSDK()
    rec = KitaruRecorder(sdk=sdk)
    await rec.start({}, name="n", metadata={})
    await rec.finish({}, error="boom")
    assert sdk.finished[0][2] == "boom"


async def test_write_evaluations():
    sdk = FakeSDK()
    rec = KitaruRecorder(sdk=sdk)
    await rec.write_evaluations("sess-1", {"coherence_rate": 0.8})
    assert sdk.evals == [("sess-1", {"coherence_rate": 0.8})]


async def test_recording_before_start_raises():
    rec = KitaruRecorder(sdk=FakeSDK())
    with pytest.raises(RuntimeError, match="start"):
        _call(rec)
