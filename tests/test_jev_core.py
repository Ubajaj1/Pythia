"""Tests for Jev core: modes, shadow collection, SDK answer conversion."""

import asyncio
from types import SimpleNamespace

from pythia.jev import core
from pythia.jev.core import ChoiceQ, NoulQ, ScoreQ, jev_mode, record_shadow, start_shadow, stop_shadow


def test_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("PYTHIA_JEV_BEHAVIOUR", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    assert jev_mode("behaviour") == "off"


def test_mode_reads_env(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.setenv("PYTHIA_JEV_COHERENCE", "shadow")
    assert jev_mode("coherence") == "shadow"


def test_mode_off_without_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("PYTHIA_JEV_COHERENCE", "primary")
    assert jev_mode("coherence") == "off"


def test_invalid_mode_is_off(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.setenv("PYTHIA_JEV_STANCE", "yes")
    assert jev_mode("stance") == "off"


async def test_shadow_collects_across_tasks():
    records, token = start_shadow()
    try:
        async def rec(i):
            record_shadow("coherence", f"a{i}", True, True, 0.9, True, "llm")
        await asyncio.gather(rec(1), rec(2))
    finally:
        stop_shadow(token)
    assert {r["key"] for r in records} == {"a1", "a2"}
    assert records[0]["piece"] == "coherence"


def test_record_without_scope_is_noop():
    record_shadow("coherence", "x", 1, 1, 1.0, True, "llm")


def test_convert_response():
    # Mirrors typesafe_sdk.SystemOneResponse: one `answers` dict keyed by question id.
    resp = SimpleNamespace(answers={
        "n": SimpleNamespace(noul=0.9),
        "c": SimpleNamespace(choice="b", confidence=0.8, probabilities={"a": 0.1, "b": 0.9}),
        "s": SimpleNamespace(score=1.5, confidence=0.6, probabilities={0: 0.1, 1: 0.4, 2: 0.5}),
    })
    qs = {"n": NoulQ("?"), "c": ChoiceQ("?", {"a": "A", "b": "B"}), "s": ScoreQ("?", ["x", "y", "z"])}
    out = core._convert(resp, qs)
    assert out["n"].value == 0.9 and abs(out["n"].confidence - 0.8) < 1e-9
    assert out["c"].value == "b" and out["c"].confidence == 0.8
    assert out["s"].value == 1.5 and out["s"].probabilities == {"0": 0.1, "1": 0.4, "2": 0.5}
