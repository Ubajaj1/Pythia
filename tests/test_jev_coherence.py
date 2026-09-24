"""Tests for Jev-assisted coherence evaluation."""

from pythia.evaluator import evaluate_agent
from pythia.jev.coherence import JEV_INCOHERENT_FALLBACK_SUMMARY
from pythia.jev.core import Answer, start_shadow, stop_shadow
from tests.conftest import FakeLLMClient
from tests.test_evaluator import make_agent, make_tick_pairs


class FakeJev:
    def __init__(self, p):
        self.p = p

    async def ask(self, state, questions):
        return {k: Answer(self.p, abs(2 * self.p - 1), {}) for k in questions}


async def test_shadow_uses_llm_and_records():
    llm = FakeLLMClient(responses=[{"is_coherent": False, "incoherence_summary": "x"}])
    records, token = start_shadow()
    try:
        ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=FakeJev(0.95), mode="shadow")
    finally:
        stop_shadow(token)
    assert ev.is_coherent is False and len(llm.calls) == 1
    assert records[0]["piece"] == "coherence" and records[0]["agree"] is False


async def test_primary_confident_coherent_skips_llm():
    llm = FakeLLMClient(responses=[])
    ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=FakeJev(0.95), mode="primary")
    assert ev.is_coherent is True and llm.calls == []


async def test_primary_confident_incoherent_asks_llm_for_summary():
    llm = FakeLLMClient(responses=[{"is_coherent": False, "incoherence_summary": "Sold while praising the asset."}])
    records, token = start_shadow()
    try:
        ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=FakeJev(0.05), mode="primary")
    finally:
        stop_shadow(token)
    assert ev.is_coherent is False and ev.incoherence_summary == "Sold while praising the asset."
    assert records[0]["llm"] is False and records[0]["agree"] is True and records[0]["used"] == "jev"


async def test_primary_incoherent_but_llm_disagrees_uses_fallback_summary():
    llm = FakeLLMClient(responses=[{"is_coherent": True, "incoherence_summary": None}])
    ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=FakeJev(0.05), mode="primary")
    assert ev.is_coherent is False and ev.incoherence_summary == JEV_INCOHERENT_FALLBACK_SUMMARY


async def test_primary_unsure_defers_to_llm():
    llm = FakeLLMClient(responses=[{"is_coherent": True, "incoherence_summary": None}])
    ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=FakeJev(0.55), mode="primary")
    assert ev.is_coherent is True and len(llm.calls) == 1


async def test_jev_error_uses_llm():
    class Boom:
        async def ask(self, state, questions):
            raise RuntimeError("down")
    llm = FakeLLMClient(responses=[{"is_coherent": True, "incoherence_summary": None}])
    ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=Boom(), mode="primary")
    assert ev.is_coherent is True and len(llm.calls) == 1
